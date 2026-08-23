"""Native backend API and persistence tests."""

import asyncio
import stat
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from backend.homelab_backend.app import (
    _resolve_supervisor_ingress_addresses,
    create_app,
)
from backend.homelab_backend.automation import (
    AutomationExecutionError,
    ExecutionResult,
    HostSnapshot,
)
from backend.homelab_backend.config import Settings
from backend.homelab_backend.models import CustomTask, Host, JobAction
from backend.homelab_backend.ssh_keys import SshKeyStore
from backend.homelab_backend.ui_sessions import (
    UI_SESSION_COOKIE,
    UI_SESSION_COOKIE_PATH,
    UiSessionStore,
)

TOKEN = "synthetic-token-with-at-least-32-characters"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class FakeExecutor:
    """Synthetic executor that never starts a process or contacts a host."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[JobAction, UUID]] = []

    async def async_execute(self, action: JobAction, host: Host) -> ExecutionResult:
        self.calls.append((action, host.id))
        if self.fail:
            raise AutomationExecutionError(
                "synthetic_failure",
                f"failed {host.address} as {host.username}",
                exit_code=2,
            )
        return ExecutionResult(
            output=f"checked {host.address} as {host.username}",
            snapshot=HostSnapshot(
                distribution="Example Linux",
                distribution_version="1.0",
                kernel="1.0.0-example",
                updates=3,
                security_updates=1,
                reboot_required=True,
                status="ok",
                checked_at=datetime(2026, 1, 15, tzinfo=UTC),
            ),
            reboot_required=True,
        )

    async def async_execute_custom(
        self, _task: CustomTask, host: Host
    ) -> ExecutionResult:
        return ExecutionResult(output=f"custom {host.address}")


class PendingExecutor(FakeExecutor):
    """Executor that remains controllably pending for queue-state assertions."""

    def __init__(self) -> None:
        super().__init__()
        self.release = asyncio.Event()

    async def async_execute(self, action: JobAction, host: Host) -> ExecutionResult:
        await self.release.wait()
        return await super().async_execute(action, host)

    async def async_release(self) -> None:
        self.release.set()


def _client(
    data_dir: Path,
    executor: FakeExecutor | None = None,
    *,
    allow_shell_tasks: bool = False,
    ingress_mode: bool = False,
    session_store: UiSessionStore | None = None,
    base_url: str = "http://testserver",
    client_host: str | None = None,
) -> TestClient:
    return TestClient(
        create_app(
            Settings(
                data_dir=data_dir,
                api_token=TOKEN,
                allow_shell_tasks=allow_shell_tasks,
                ingress_mode=ingress_mode,
            ),
            executor=executor,
            session_store=session_store,
            ingress_proxy_addresses=(
                frozenset({"supervisor-proxy"}) if ingress_mode else None
            ),
        ),
        base_url=base_url,
        client=(
            client_host or ("supervisor-proxy" if ingress_mode else "testclient"),
            50000,
        ),
    )


def _csrf(client: TestClient) -> str:
    page = client.get("/")
    return page.text.split('name="csrf-token" content="', 1)[1].split('"', 1)[0]


def _ui_login(client: TestClient, csrf: str, token: str = TOKEN) -> None:
    response = client.post(
        "/ui-api/auth/login",
        headers={"X-CSRF-Token": csrf},
        json={"api_token": token},
    )
    assert response.status_code == 200


def _create_host(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/hosts",
        headers=AUTH,
        json={
            "name": "Node 01",
            "address": "node-01.example.invalid",
            "username": "automation",
        },
    )
    assert response.status_code == 201
    return response.json()  # type: ignore[no-any-return]


def _terminal_job(client: TestClient, job_id: str) -> dict[str, object]:
    for _attempt in range(100):
        payload = client.get(f"/api/v1/jobs/{job_id}", headers=AUTH).json()
        if payload["state"] in {"success", "failed"}:
            return payload  # type: ignore[no-any-return]
    raise AssertionError("Synthetic job did not reach a terminal state")


def test_health_is_public_but_inventory_requires_auth(tmp_path: Path) -> None:
    """Probes work without secrets while managed data remains protected."""
    with _client(tmp_path) as client:
        assert client.get("/api/v1/health").json() == {"status": "ok"}
        assert client.get("/api/v1/info").status_code == 401
        assert (
            client.get(
                "/api/v1/hosts", headers={"Authorization": "Bearer wrong-token"}
            ).status_code
            == 401
        )
        info = client.get("/api/v1/info", headers=AUTH)
        assert info.status_code == 200
        assert info.json()["api_version"] == "v1"


def test_host_crud_preserves_uuid_and_persists(tmp_path: Path) -> None:
    """Host identity survives edits and application restarts."""
    payload = {
        "name": "Node 01",
        "address": "node-01.example.invalid",
        "username": "automation",
    }
    with _client(tmp_path) as client:
        created = client.post("/api/v1/hosts", headers=AUTH, json=payload)
        assert created.status_code == 201
        host_id = UUID(created.json()["id"])
        assert created.json()["port"] == 22

        duplicate = client.post("/api/v1/hosts", headers=AUTH, json=payload)
        assert duplicate.status_code == 409

        patched = client.patch(
            f"/api/v1/hosts/{host_id}",
            headers=AUTH,
            json={"name": "Renamed node", "port": 2222},
        )
        assert patched.status_code == 200
        assert UUID(patched.json()["id"]) == host_id
        assert patched.json()["name"] == "Renamed node"
        assert patched.json()["port"] == 2222

    with _client(tmp_path) as restarted:
        hosts = restarted.get("/api/v1/hosts", headers=AUTH).json()
        assert len(hosts) == 1
        assert UUID(hosts[0]["id"]) == host_id
        assert (
            restarted.delete(f"/api/v1/hosts/{host_id}", headers=AUTH).status_code
            == 204
        )
        assert (
            restarted.get(f"/api/v1/hosts/{host_id}", headers=AUTH).status_code == 404
        )


def test_host_validation_is_strict(tmp_path: Path) -> None:
    """Unexpected fields and unsafe SSH values fail at the API boundary."""
    with _client(tmp_path) as client:
        response = client.post(
            "/api/v1/hosts",
            headers=AUTH,
            json={
                "name": "Node 01",
                "address": "node-01.example.invalid",
                "username": "root; touch unsafe",
                "password": "must-never-be-accepted",
            },
        )
        assert response.status_code == 422


def test_managed_ed25519_key_is_stable_private_and_public_only(
    tmp_path: Path,
) -> None:
    """The API never exposes private key material and file mode stays 0600."""
    with _client(tmp_path) as client:
        first = client.get("/api/v1/public-key", headers=AUTH)
        second = client.get("/api/v1/public-key", headers=AUTH)

    assert first.status_code == 200
    assert first.json() == second.json()
    assert first.json()["public_key"].startswith("ssh-ed25519 ")
    assert "PRIVATE" not in first.text
    private_path = tmp_path / "ssh" / "id_ed25519"
    assert stat.S_IMODE(private_path.stat().st_mode) == 0o600
    assert "PRIVATE KEY" in private_path.read_text()


def test_managed_key_rejects_an_unexpected_key_algorithm(tmp_path: Path) -> None:
    """A substituted non-ED25519 key cannot cross the managed-key boundary."""
    path = tmp_path / "id_ed25519"
    path.write_text("synthetic")
    store = SshKeyStore(path)
    with (
        patch(
            "backend.homelab_backend.ssh_keys.subprocess.run",
            return_value=subprocess.CompletedProcess(
                [], 0, stdout=b"ssh-rsa synthetic\n", stderr=b""
            ),
        ),
        pytest.raises(ValueError, match="not ED25519"),
    ):
        store._public_key()


def test_managed_key_reports_generation_failure_without_process_output(
    tmp_path: Path,
) -> None:
    """OpenSSH failures expose neither command output nor partial key data."""
    store = SshKeyStore(tmp_path / "id_ed25519")
    with (
        patch(
            "backend.homelab_backend.ssh_keys.subprocess.run",
            return_value=subprocess.CompletedProcess(
                [], 1, stdout=b"synthetic output", stderr=b"synthetic detail"
            ),
        ),
        pytest.raises(ValueError, match="Could not generate"),
    ):
        store._ensure()


def test_missing_hosts_return_not_found(tmp_path: Path) -> None:
    """All UUID-addressed mutations report an absent target consistently."""
    host_id = "00000000-0000-4000-8000-000000000001"
    with _client(tmp_path) as client:
        assert client.get(f"/api/v1/hosts/{host_id}", headers=AUTH).status_code == 404
        assert (
            client.patch(
                f"/api/v1/hosts/{host_id}", headers=AUTH, json={"name": "Node"}
            ).status_code
            == 404
        )
        assert (
            client.delete(f"/api/v1/hosts/{host_id}", headers=AUTH).status_code == 404
        )


def test_actions_are_queued_and_update_status_without_implicit_reboot(
    tmp_path: Path,
) -> None:
    """Action requests return jobs and update status; only requested action runs."""
    executor = FakeExecutor()
    with _client(tmp_path, executor) as client:
        host = _create_host(client)
        host_id = str(host["id"])
        response = client.post(f"/api/v1/hosts/{host_id}/actions/update", headers=AUTH)
        assert response.status_code == 202
        job = _terminal_job(client, response.json()["id"])
        assert job["state"] == "success"
        assert job["job_id"] == job["id"]
        assert job["type"] == "update"
        assert job["host_name"] == "Node 01"
        assert job["exit_code"] == 0
        assert job["duration"] >= 0
        assert job["log_available"] is True
        assert job["reboot_required"] is True
        assert executor.calls == [(JobAction.UPDATE, UUID(host_id))]

        updated = client.get(f"/api/v1/hosts/{host_id}", headers=AUTH).json()
        assert updated["updates"] == 3
        assert updated["security_updates"] == 1
        assert updated["reboot_required"] is True
        assert updated["checked_at"] == "2026-01-15T00:00:00Z"

        log = client.get(f"/api/v1/jobs/{job['id']}/log", headers=AUTH).json()
        assert "node-01.example.invalid" not in log["output"]
        assert "automation" not in log["output"]
        assert log["output"] == "checked [redacted] as [redacted]"


def test_failed_job_uses_safe_error_code_and_redacted_log(tmp_path: Path) -> None:
    """Executor failures persist without leaking connection details."""
    executor = FakeExecutor(fail=True)
    with _client(tmp_path, executor) as client:
        host_id = str(_create_host(client)["id"])
        response = client.post(
            f"/api/v1/hosts/{host_id}/actions/test-connection", headers=AUTH
        )
        job = _terminal_job(client, response.json()["id"])
        assert job["state"] == "failed"
        assert job["exit_code"] == 2
        assert job["error_code"] == "synthetic_failure"
        assert job["short_error"] == "Synthetic failure"
        log = client.get(f"/api/v1/jobs/{job['id']}/log", headers=AUTH).json()
        assert log["output"] == "failed [redacted] as [redacted]"


def test_global_check_queues_one_exact_job_per_host(tmp_path: Path) -> None:
    """A global check expands to explicit host-targeted jobs."""
    executor = FakeExecutor()
    with _client(tmp_path, executor) as client:
        host = _create_host(client)
        response = client.post("/api/v1/actions/check", headers=AUTH)
        assert response.status_code == 202
        jobs = response.json()
        assert len(jobs) == 1
        assert jobs[0]["host_id"] == host["id"]


def test_action_for_unknown_host_fails_before_queueing(tmp_path: Path) -> None:
    """Mutating and read-only host actions both reject unknown targets."""
    with _client(tmp_path, FakeExecutor()) as client:
        host_id = "00000000-0000-4000-8000-000000000001"
        assert (
            client.post(
                f"/api/v1/hosts/{host_id}/actions/reboot", headers=AUTH
            ).status_code
            == 404
        )
        assert client.get("/api/v1/jobs", headers=AUTH).json() == []


def test_custom_task_crud_and_exact_host_execution(tmp_path: Path) -> None:
    """Command tasks use structured argv and queue against one host UUID."""
    executor = FakeExecutor()
    with _client(tmp_path, executor) as client:
        host_id = str(_create_host(client)["id"])
        created = client.post(
            "/api/v1/custom-tasks",
            headers=AUTH,
            json={
                "name": "Read service status",
                "description": "Synthetic task",
                "mode": "command",
                "argv": ["systemctl", "is-active", "example.service"],
            },
        )
        assert created.status_code == 201
        task_id = created.json()["id"]
        assert created.json()["shell_command"] is None
        assert len(client.get("/api/v1/custom-tasks", headers=AUTH).json()) == 1

        patched = client.patch(
            f"/api/v1/custom-tasks/{task_id}",
            headers=AUTH,
            json={"name": "Check service status"},
        )
        assert patched.status_code == 200
        assert patched.json()["id"] == task_id

        queued = client.post(
            f"/api/v1/hosts/{host_id}/actions/tasks/{task_id}", headers=AUTH
        )
        assert queued.status_code == 202
        job = _terminal_job(client, queued.json()["id"])
        assert job["action"] == "custom_task"
        assert job["custom_task_id"] == task_id

        assert (
            client.delete(f"/api/v1/custom-tasks/{task_id}", headers=AUTH).status_code
            == 204
        )


def test_shell_tasks_are_explicitly_disabled_by_default(tmp_path: Path) -> None:
    """Shell semantics need a deployment-level opt-in in addition to task mode."""
    payload = {
        "name": "Shell example",
        "mode": "shell",
        "shell_command": "printf synthetic",
    }
    with _client(tmp_path, FakeExecutor()) as client:
        assert (
            client.post("/api/v1/custom-tasks", headers=AUTH, json=payload).status_code
            == 403
        )
    with _client(
        tmp_path / "enabled", FakeExecutor(), allow_shell_tasks=True
    ) as client:
        assert (
            client.post("/api/v1/custom-tasks", headers=AUTH, json=payload).status_code
            == 201
        )


def test_custom_task_validation_rejects_ambiguous_execution(tmp_path: Path) -> None:
    """A task cannot silently mix argv and shell command semantics."""
    with _client(tmp_path, FakeExecutor()) as client:
        response = client.post(
            "/api/v1/custom-tasks",
            headers=AUTH,
            json={
                "name": "Ambiguous",
                "mode": "command",
                "argv": ["true"],
                "shell_command": "false",
            },
        )
        assert response.status_code == 422


def test_ingress_ui_uses_supervisor_boundary_and_csrf(tmp_path: Path) -> None:
    """Ingress can read UI data without exposing the token; mutations need CSRF."""
    with _client(tmp_path, FakeExecutor(), ingress_mode=True) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert TOKEN not in page.text
        assert 'name="api-base" content="ui-api/"' in page.text
        assert 'src="./ui.js"' in page.text
        assert "onclick=" not in page.text
        assert "script-src 'self'" in page.headers["content-security-policy"]
        assert client.get("/ui.js").status_code == 200
        assert client.get("/ui.css").status_code == 200
        csrf = page.text.split('name="csrf-token" content="', 1)[1].split('"', 1)[0]
        assert client.get("/ui-api/snapshot").status_code == 200
        assert client.get("/ui-api/info").status_code == 200
        assert client.get("/ui-api/hosts").status_code == 200
        assert client.get("/ui-api/public-key").status_code == 200
        assert client.get("/ui-api/custom-tasks").status_code == 200
        assert client.get("/ui-api/jobs").status_code == 200
        assert client.get("/ui-api/auth/session").status_code == 404
        assert (
            client.post(
                "/ui-api/auth/login",
                headers={"X-CSRF-Token": csrf},
                json={"api_token": TOKEN},
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/ui-api/auth/logout", headers={"X-CSRF-Token": csrf}
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/ui-api/hosts",
                json={
                    "name": "Node 01",
                    "address": "node-01.example.invalid",
                    "username": "automation",
                },
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/ui-api/hosts",
                headers={"X-CSRF-Token": csrf},
                json={
                    "name": "Node 01",
                    "address": "node-01.example.invalid",
                    "username": "automation",
                },
            ).status_code
            == 201
        )

        assert client.get("/api/v1/info").status_code == 401
        assert client.get("/api/v1/info", headers=AUTH).status_code == 200


def test_ingress_ui_rejects_requests_outside_supervisor_proxy(tmp_path: Path) -> None:
    """Ingress trust never makes management routes public on the app port."""
    with _client(
        tmp_path,
        FakeExecutor(),
        ingress_mode=True,
        client_host="192.0.2.10",
    ) as client:
        assert client.get("/").status_code == 403
        assert client.get("/ui.js").status_code == 403
        assert client.get("/ui.css").status_code == 403
        assert client.get("/ui-api/info").status_code == 403
        assert client.get("/api/v1/info").status_code == 401
        assert client.get("/api/v1/info", headers=AUTH).status_code == 200


def test_ingress_resolves_stable_supervisor_alias_at_startup(tmp_path: Path) -> None:
    """Production Ingress trust derives from Supervisor DNS, not a stored IP."""
    resolver = AsyncMock(return_value=frozenset({"resolved-supervisor-proxy"}))
    app = create_app(
        Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=True),
        executor=FakeExecutor(),
    )
    with (
        patch(
            "backend.homelab_backend.app._resolve_supervisor_ingress_addresses",
            resolver,
        ),
        TestClient(app, client=("resolved-supervisor-proxy", 50000)) as client,
    ):
        assert client.get("/").status_code == 200
        assert client.get("/ui-api/info").status_code == 200
    resolver.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_ingress_proxy_address_resolution_filters_non_ip_results() -> None:
    """Supervisor resolution accepts only concrete string addresses."""
    getaddrinfo = AsyncMock(
        return_value=[
            (2, 1, 6, "", ("198.51.100.1", 0)),
            (1, 1, 0, "", (7,)),
        ]
    )
    with patch.object(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo):
        assert await _resolve_supervisor_ingress_addresses() == frozenset({
            "198.51.100.1"
        })


@pytest.mark.asyncio
async def test_ingress_proxy_address_resolution_fails_closed_on_dns_error() -> None:
    """Ingress does not start when the trusted Supervisor source is unknown."""
    getaddrinfo = AsyncMock(side_effect=OSError("synthetic DNS failure"))
    with (
        patch.object(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo),
        pytest.raises(RuntimeError, match="Unable to resolve"),
    ):
        await _resolve_supervisor_ingress_addresses()


@pytest.mark.asyncio
async def test_ingress_proxy_address_resolution_fails_closed_without_ip() -> None:
    """Non-IP resolver results cannot accidentally authorize Ingress traffic."""
    getaddrinfo = AsyncMock(return_value=[(1, 1, 0, "", (7,))])
    with (
        patch.object(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo),
        pytest.raises(RuntimeError, match="without an IP address"),
    ):
        await _resolve_supervisor_ingress_addresses()


def test_standalone_ui_uses_short_lived_cookie_session_and_csrf(
    tmp_path: Path,
) -> None:
    """UI sessions remain separate from external Bearer authentication."""
    with _client(tmp_path, FakeExecutor()) as client:
        page = client.get("/")
        assert 'name="api-base" content="ui-api/"' in page.text
        assert page.headers["cache-control"] == "no-store"
        csrf = _csrf(client)
        assert client.get("/ui-api/snapshot").status_code == 401
        assert client.get("/ui-api/snapshot", headers=AUTH).status_code == 401
        assert (
            client.post("/ui-api/auth/login", json={"api_token": TOKEN}).status_code
            == 403
        )
        rejected = client.post(
            "/ui-api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"api_token": "wrong-token-that-is-at-least-32-characters"},
        )
        assert rejected.status_code == 401
        assert UI_SESSION_COOKIE not in client.cookies

        login = client.post(
            "/ui-api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"api_token": TOKEN},
        )
        assert login.json() == {"authenticated": True}
        cookie_header = login.headers["set-cookie"]
        assert f"{UI_SESSION_COOKIE}=" in cookie_header
        assert f"Path={UI_SESSION_COOKIE_PATH}" in cookie_header
        assert "HttpOnly" in cookie_header
        assert "SameSite=strict" in cookie_header
        assert "Secure" not in cookie_header
        assert TOKEN not in cookie_header
        assert client.get("/ui-api/auth/session").json() == {"authenticated": True}
        assert client.get("/ui-api/snapshot").status_code == 200

        assert client.get("/api/v1/info").status_code == 401
        assert client.get("/api/v1/info", headers=AUTH).status_code == 200
        assert client.post("/ui-api/hosts", json={}).status_code == 403

        assert client.post("/ui-api/auth/logout").status_code == 403
        logout = client.post("/ui-api/auth/logout", headers={"X-CSRF-Token": csrf})
        assert logout.status_code == 204
        assert client.get("/ui-api/auth/session").status_code == 401
        assert client.get("/ui-api/snapshot").status_code == 401


def test_ui_session_cookie_is_secure_on_https_and_invalid_cookie_is_cleared(
    tmp_path: Path,
) -> None:
    """Transport-aware cookies fail closed without storing the API token."""
    with _client(tmp_path, FakeExecutor(), base_url="https://testserver") as client:
        csrf = _csrf(client)
        _ui_login(client, csrf)
        login = client.post(
            "/ui-api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"api_token": TOKEN},
        )
        assert "Secure" in login.headers["set-cookie"]

        client.cookies.set(
            UI_SESSION_COOKIE,
            "invalid-opaque-session",
            path=UI_SESSION_COOKIE_PATH,
        )
        expired = client.get("/ui-api/auth/session")
        assert expired.status_code == 401
        assert expired.json() == {"authenticated": False}
        assert f'{UI_SESSION_COOKIE}=""' in expired.headers["set-cookie"]


def test_api_reports_conflicts_missing_jobs_and_missing_tasks(tmp_path: Path) -> None:
    """Conflict and not-found branches remain stable public API contracts."""
    missing_id = "00000000-0000-4000-8000-000000000001"
    executor = PendingExecutor()
    with _client(tmp_path, executor) as client:
        first = _create_host(client)
        second = client.post(
            "/api/v1/hosts",
            headers=AUTH,
            json={
                "name": "Node 02",
                "address": "node-02.example.invalid",
                "username": "automation",
            },
        ).json()
        duplicate_patch = client.patch(
            f"/api/v1/hosts/{second['id']}",
            headers=AUTH,
            json={"address": "node-01.example.invalid"},
        )
        assert duplicate_patch.status_code == 409

        assert client.get(f"/api/v1/jobs/{missing_id}", headers=AUTH).status_code == 404
        assert (
            client.get(f"/api/v1/jobs/{missing_id}/log", headers=AUTH).status_code
            == 404
        )
        assert client.get(f"/api/v1/jobs/{missing_id}/log").status_code == 401

        pending = client.post(
            f"/api/v1/hosts/{first['id']}/actions/check-updates", headers=AUTH
        ).json()
        try:
            pending_log = client.get(
                f"/api/v1/jobs/{pending['id']}/log", headers=AUTH
            ).json()
            assert pending_log["output"] == ""
        finally:
            assert client.portal is not None
            client.portal.call(executor.async_release)

        assert (
            client.patch(
                f"/api/v1/custom-tasks/{missing_id}",
                headers=AUTH,
                json={"name": "Missing"},
            ).status_code
            == 404
        )
        assert (
            client.delete(
                f"/api/v1/custom-tasks/{missing_id}", headers=AUTH
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/v1/hosts/{first['id']}/actions/tasks/{missing_id}",
                headers=AUTH,
            ).status_code
            == 404
        )


def test_disabled_and_shell_task_mutations_fail_closed(tmp_path: Path) -> None:
    """Disabled execution and shell-mode patches require explicit policy changes."""
    with _client(tmp_path, FakeExecutor()) as client:
        host_id = _create_host(client)["id"]
        task = client.post(
            "/api/v1/custom-tasks",
            headers=AUTH,
            json={
                "name": "Disabled task",
                "mode": "command",
                "argv": ["true"],
                "enabled": False,
            },
        ).json()
        assert (
            client.post(
                f"/api/v1/hosts/{host_id}/actions/tasks/{task['id']}", headers=AUTH
            ).status_code
            == 409
        )
        assert (
            client.patch(
                f"/api/v1/custom-tasks/{task['id']}",
                headers=AUTH,
                json={
                    "mode": "shell",
                    "argv": None,
                    "shell_command": "printf synthetic",
                },
            ).status_code
            == 403
        )


def test_ingress_management_routes_cover_crud_actions_and_errors(
    tmp_path: Path,
) -> None:
    """Ingress management delegates to the same repositories and queue policy."""
    missing_id = "00000000-0000-4000-8000-000000000001"
    with _client(tmp_path, FakeExecutor(), ingress_mode=True) as client:
        page = client.get("/").text
        csrf = page.split('name="csrf-token" content="', 1)[1].split('"', 1)[0]
        headers = {"X-CSRF-Token": csrf}
        host_payload = {
            "name": "Node 01",
            "address": "node-01.example.invalid",
            "username": "automation",
        }
        host = client.post("/ui-api/hosts", headers=headers, json=host_payload).json()
        assert (
            client.post("/ui-api/hosts", headers=headers, json=host_payload).status_code
            == 409
        )
        assert (
            client.patch(
                f"/ui-api/hosts/{host['id']}",
                headers=headers,
                json={"name": "Renamed node"},
            ).json()["name"]
            == "Renamed node"
        )
        assert (
            client.patch(
                f"/ui-api/hosts/{missing_id}",
                headers=headers,
                json={"name": "Missing"},
            ).status_code
            == 404
        )

        task_payload = {
            "name": "Read uptime",
            "mode": "command",
            "argv": ["uptime"],
        }
        task = client.post(
            "/ui-api/custom-tasks", headers=headers, json=task_payload
        ).json()
        assert (
            client.patch(
                f"/ui-api/custom-tasks/{task['id']}",
                headers=headers,
                json={"name": "Read system uptime"},
            ).json()["name"]
            == "Read system uptime"
        )
        assert (
            client.patch(
                f"/ui-api/custom-tasks/{missing_id}",
                headers=headers,
                json={"name": "Missing"},
            ).status_code
            == 404
        )
        assert (
            client.patch(
                f"/ui-api/custom-tasks/{task['id']}",
                headers=headers,
                json={
                    "mode": "shell",
                    "argv": None,
                    "shell_command": "printf synthetic",
                },
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/ui-api/custom-tasks",
                headers=headers,
                json={
                    "name": "Shell",
                    "mode": "shell",
                    "shell_command": "printf synthetic",
                },
            ).status_code
            == 403
        )
        ui_job = client.post(
            f"/ui-api/hosts/{host['id']}/actions/test_connection",
            headers=headers,
        )
        assert ui_job.status_code == 202
        terminal = _terminal_job(client, ui_job.json()["id"])
        assert (
            client.get(
                f"/ui-api/jobs/{terminal['id']}/log", headers=headers
            ).status_code
            == 200
        )
        metadata = client.get(f"/ui-api/jobs/{terminal['id']}", headers=headers)
        assert metadata.status_code == 200
        assert metadata.json()["job_id"] == terminal["id"]
        assert (
            client.get(f"/ui-api/jobs/{missing_id}/log", headers=headers).status_code
            == 404
        )
        assert (
            client.get(f"/ui-api/jobs/{missing_id}", headers=headers).status_code == 404
        )
        assert (
            client.post(
                f"/ui-api/hosts/{host['id']}/actions/custom_task", headers=headers
            ).status_code
            == 422
        )
        assert (
            client.post(
                f"/ui-api/hosts/{host['id']}/tasks/{task['id']}", headers=headers
            ).status_code
            == 202
        )
        assert (
            client.post(
                f"/ui-api/hosts/{host['id']}/tasks/{missing_id}", headers=headers
            ).status_code
            == 404
        )
        disabled_task = client.post(
            "/ui-api/custom-tasks",
            headers=headers,
            json={
                "name": "Disabled",
                "mode": "command",
                "argv": ["true"],
                "enabled": False,
            },
        ).json()
        assert (
            client.post(
                f"/ui-api/hosts/{host['id']}/tasks/{disabled_task['id']}",
                headers=headers,
            ).status_code
            == 409
        )
        assert (
            client.delete(
                f"/ui-api/custom-tasks/{task['id']}", headers=headers
            ).status_code
            == 204
        )
        assert (
            client.delete(
                f"/ui-api/custom-tasks/{missing_id}", headers=headers
            ).status_code
            == 404
        )
        assert (
            client.delete(f"/ui-api/hosts/{host['id']}", headers=headers).status_code
            == 204
        )
        assert (
            client.delete(f"/ui-api/hosts/{missing_id}", headers=headers).status_code
            == 404
        )
