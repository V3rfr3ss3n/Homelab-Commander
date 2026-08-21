"""Native backend API and persistence tests."""

import stat
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from backend.homelab_backend.app import create_app
from backend.homelab_backend.automation import (
    AutomationExecutionError,
    ExecutionResult,
    HostSnapshot,
)
from backend.homelab_backend.config import Settings
from backend.homelab_backend.models import CustomTask, Host, JobAction
from backend.homelab_backend.ssh_keys import SshKeyStore

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
                "synthetic_failure", f"failed {host.address} as {host.username}"
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


def _client(
    data_dir: Path,
    executor: FakeExecutor | None = None,
    *,
    allow_shell_tasks: bool = False,
    ingress_mode: bool = False,
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
        )
    )


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
        assert job["error_code"] == "synthetic_failure"
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
        csrf = page.text.split('name="csrf-token" content="', 1)[1].split('"', 1)[0]
        assert client.get("/ui-api/snapshot").status_code == 200
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


def test_standalone_ui_api_requires_bearer_token(tmp_path: Path) -> None:
    """The UI bridge cannot bypass authentication outside Supervisor Ingress."""
    with _client(tmp_path, FakeExecutor()) as client:
        assert client.get("/ui-api/snapshot").status_code == 401
        assert client.get("/ui-api/snapshot", headers=AUTH).status_code == 200


def test_api_reports_conflicts_missing_jobs_and_missing_tasks(tmp_path: Path) -> None:
    """Conflict and not-found branches remain stable public API contracts."""
    missing_id = "00000000-0000-4000-8000-000000000001"
    with _client(tmp_path, FakeExecutor()) as client:
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

        pending = client.post(
            f"/api/v1/hosts/{first['id']}/actions/check-updates", headers=AUTH
        ).json()
        pending_log = client.get(
            f"/api/v1/jobs/{pending['id']}/log", headers=AUTH
        ).json()
        assert pending_log["output"] == ""

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
        assert (
            client.get(f"/ui-api/jobs/{missing_id}/log", headers=headers).status_code
            == 404
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
