"""Bounded package detail models, persistence and read-only endpoints."""

import asyncio
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from backend.homelab_backend.automation import (
    AutomationExecutionError,
    ExecutionResult,
    HostSnapshot,
)
from backend.homelab_backend.custom_tasks import CustomTaskRepository
from backend.homelab_backend.database import _MIGRATIONS, Database
from backend.homelab_backend.hosts import HostRepository
from backend.homelab_backend.jobs import JobManager, JobRepository
from backend.homelab_backend.models import (
    Host,
    HostCreate,
    JobAction,
    JobState,
    PackageInfo,
    PackagesResponse,
)
from backend.homelab_backend.package_providers import DebianAptProvider
from backend.tests.test_backend_api import (
    AUTH,
    TOKEN,
    FakeExecutor,
    _client,
    _csrf,
    _terminal_job,
)


def test_package_response_model_shape() -> None:
    package = PackageInfo(name="curl", old_version="8.3.0-1", new_version="8.8.0-1")
    response = PackagesResponse(
        packages=(package,), total=17, checked_at=None, provider="debian_apt"
    )
    assert response.model_dump(mode="json") == {
        "packages": [
            {
                "name": "curl",
                "old_version": "8.3.0-1",
                "new_version": "8.8.0-1",
                "is_security": False,
            }
        ],
        "total": 17,
        "security_updates": 0,
        "checked_at": None,
        "provider": "debian_apt",
    }


async def test_package_counts_persist_and_rows_are_disposable(tmp_path: Path) -> None:
    database = Database(tmp_path / "packages.db")
    await database.async_migrate()
    hosts = HostRepository(database)
    host = await hosts.async_create(
        HostCreate(
            name="Node 01", address="node-01.example.invalid", username="automation"
        )
    )
    assert host.packages == ()
    package = PackageInfo(
        name="curl", old_version="1", new_version="2", is_security=True
    )
    checked = datetime(2026, 11, 11, 12, tzinfo=UTC)
    await hosts.async_update_status(
        host.id,
        distribution="Debian",
        distribution_version="13",
        kernel="6.1",
        updates=1,
        security_updates=1,
        reboot_required=False,
        status="ok",
        checked_at=checked,
        packages=(package,),
    )
    loaded = await hosts.async_get(host.id)
    assert loaded is not None
    assert loaded.packages == (package,)
    assert loaded.checked_at == checked
    reopened = await HostRepository(database).async_get(host.id)
    assert reopened.packages == ()
    assert reopened.updates == 1
    empty = await hosts.async_create(
        HostCreate(
            name="Node 02", address="node-02.example.invalid", username="automation"
        )
    )
    assert (await hosts.async_get(empty.id)).packages == ()  # type: ignore[union-attr]


def test_package_endpoints_auth_and_response_shape(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        host = client.post(
            "/api/v1/hosts",
            headers=AUTH,
            json={
                "name": "Node 01",
                "address": "node-01.example.invalid",
                "username": "automation",
            },
        ).json()
        path = f"/api/v1/hosts/{host['id']}/packages"
        assert client.get(path).status_code == 401
        assert client.get(path, headers=AUTH).json() == {
            "packages": [],
            "total": 0,
            "security_updates": 0,
            "checked_at": None,
            "provider": None,
        }
        assert (
            client.get(
                "/api/v1/hosts/00000000-0000-4000-8000-000000000000/packages",
                headers=AUTH,
            ).status_code
            == 404
        )
        assert "packages" not in client.get("/api/v1/hosts", headers=AUTH).json()[0]

        assert client.get(f"/ui-api/hosts/{host['id']}/packages").status_code == 401
        assert (
            client.get(
                f"/ui-api/hosts/{host['id']}/packages",
                headers={"Cookie": "hlc_ui_session=wrong"},
            ).status_code
            == 401
        )
        login = client.post(
            "/ui-api/auth/login",
            headers={"X-CSRF-Token": _csrf(client)},
            json={"api_token": TOKEN},
        )
        assert login.status_code == 200
        assert client.get(f"/ui-api/hosts/{host['id']}/packages").status_code == 200
        assert (
            client.get(
                "/ui-api/hosts/00000000-0000-4000-8000-000000000000/packages"
            ).status_code
            == 404
        )
        assert client.get("/ui-api/hosts").json()[0].get("packages") is None
    with _client(
        tmp_path / "ingress", ingress_mode=True, client_host="untrusted-proxy"
    ) as client:
        assert (
            client.get(
                "/ui-api/hosts/00000000-0000-4000-8000-000000000000/packages"
            ).status_code
            == 403
        )


class PackageExecutor(FakeExecutor):
    """Stateful synthetic package adapter; scoped updates keep other packages."""

    def __init__(self) -> None:
        super().__init__()
        self.scopes: list[tuple[str, ...] | None] = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.release.set()

    async def async_execute(
        self,
        action: JobAction,
        host: Host,
        package_name: str | None = None,
        *,
        package_names: tuple[str, ...] = (),
    ) -> ExecutionResult:
        self.started.set()
        await self.release.wait()
        if self.fail:
            raise AutomationExecutionError(
                "update_packages_failed", "Synthetic failure"
            )
        scope = package_names or ((package_name,) if package_name else ())
        self.scopes.append(scope or None)
        remaining = (
            tuple(p for p in host.packages if p.name not in scope)
            if action is JobAction.UPDATE and scope
            else ()
            if action is JobAction.UPDATE
            else host.packages
        )
        return ExecutionResult(
            output="Synthetic package update; no command executed.",
            snapshot=HostSnapshot(
                distribution="Debian",
                distribution_version="12",
                kernel="synthetic",
                updates=len(remaining),
                security_updates=sum(p.is_security for p in remaining),
                reboot_required=True,
                status="ok",
                checked_at=datetime.now(UTC),
                packages=remaining,
            ),
        )


@pytest.mark.parametrize("scope", ["single", "selected", "all"])
async def test_package_update_recovery_preserves_scope_and_snapshot(
    tmp_path: Path, scope: str
) -> None:
    database = Database(tmp_path / "scoped.db")
    await database.async_migrate()
    hosts = HostRepository(database)
    host = await hosts.async_create(
        HostCreate(
            name="Node 01", address="node-01.example.invalid", username="automation"
        )
    )
    packages = tuple(
        PackageInfo(name=n, old_version="1", new_version="2", is_security=n == "curl")
        for n in ("curl", "git", "openssl", *(f"package-{i}" for i in range(9)))
    )
    await hosts.async_update_status(
        host.id,
        distribution="Debian",
        distribution_version="12",
        kernel="synthetic",
        updates=12,
        security_updates=1,
        reboot_required=False,
        status="ok",
        checked_at=datetime.now(UTC),
        packages=packages,
    )
    jobs = JobRepository(database)
    queued = await jobs.async_create(
        JobAction.UPDATE,
        host.id,
        package_name="curl" if scope == "single" else None,
        package_names=("curl", "git") if scope == "selected" else (),
    )
    executor = PackageExecutor()
    executor.release.clear()
    manager = JobManager(
        jobs, hosts, CustomTaskRepository(database, allow_shell=False), executor
    )
    await manager.async_start()
    try:
        await executor.started.wait()
        assert (await hosts.async_get(host.id)).updates == 12
        executor.release.set()
        await manager.async_wait_idle()
        updated = await hosts.async_get(host.id)
        assert updated is not None
        removed = (
            {"curl"}
            if scope == "single"
            else {"curl", "git"}
            if scope == "selected"
            else {p.name for p in packages}
        )
        expected = tuple(p.name for p in packages if p.name not in removed)
        assert tuple(p.name for p in updated.packages) == expected
        assert updated.updates == len(expected)
        assert updated.security_updates == 0
        assert updated.reboot_required
        assert (await jobs.async_get(queued.id)).state is JobState.SUCCESS
        assert executor.scopes == [
            ("curl",)
            if scope == "single"
            else ("curl", "git")
            if scope == "selected"
            else None
        ]
    finally:
        executor.release.set()
        await manager.async_stop()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"package_names": []},
        {"package_names": ["curl", "curl"]},
        {"package_names": ["curl;reboot"]},
        {"package_name": "curl", "package_names": ["git"]},
        {"package_names": [f"package-{i}" for i in range(51)]},
    ],
)
def test_invalid_package_scopes_never_queue_work(
    tmp_path: Path, body: dict[str, object]
) -> None:
    with _client(tmp_path) as client:
        host = client.post(
            "/api/v1/hosts",
            headers=AUTH,
            json={
                "name": "Node 01",
                "address": "node-01.example.invalid",
                "username": "automation",
            },
        ).json()
        assert (
            client.post(
                f"/api/v1/hosts/{host['id']}/actions/update", headers=AUTH, json=body
            ).status_code
            == 422
        )
        assert client.get("/api/v1/jobs", headers=AUTH).json() == []


def test_selected_package_api_and_ui_share_the_persisted_scope(tmp_path: Path) -> None:
    with _client(tmp_path, PackageExecutor(), ingress_mode=True) as client:
        host = client.post(
            "/api/v1/hosts",
            headers=AUTH,
            json={
                "name": "Node 01",
                "address": "node-01.example.invalid",
                "username": "automation",
            },
        ).json()
        csrf = _csrf(client)
        for prefix, headers in (("/api/v1", AUTH), ("/ui-api", {"X-CSRF-Token": csrf})):
            response = client.post(
                f"{prefix}/hosts/{host['id']}/actions/update",
                headers=headers,
                json={"package_names": ["curl", "git"]},
            )
            assert response.status_code == 202
            job = _terminal_job(client, response.json()["id"])
            assert job["package_names"] == ["curl", "git"]
            assert job["package_name"] is None
            assert job["state"] == "success"
        assert (
            client.post(
                f"/ui-api/hosts/{host['id']}/actions/reboot",
                headers={"X-CSRF-Token": csrf},
                json={"package_name": "curl"},
            ).status_code
            == 422
        )


async def test_package_review_resolution_requires_the_same_scope(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "review.db")
    await database.async_migrate()
    host = await HostRepository(database).async_create(
        HostCreate(
            name="Node 01", address="node-01.example.invalid", username="automation"
        )
    )
    jobs = JobRepository(database)
    failed = await jobs.async_create(
        JobAction.UPDATE, host.id, package_names=("git", "curl")
    )
    await jobs.async_finish(
        failed.id, state=JobState.FAILED, output="Synthetic failure", truncated=False
    )
    other = await jobs.async_create(
        JobAction.UPDATE, host.id, package_names=("openssl",)
    )
    await jobs.async_finish(
        other.id, state=JobState.SUCCESS, output="Synthetic success", truncated=False
    )
    assert (await jobs.async_get(failed.id)).needs_review
    matching = await jobs.async_create(
        JobAction.UPDATE, host.id, package_names=("curl", "git")
    )
    await jobs.async_finish(
        matching.id, state=JobState.SUCCESS, output="Synthetic success", truncated=False
    )
    assert not (await jobs.async_get(failed.id)).needs_review


@pytest.mark.parametrize("version", [7, 9])
async def test_package_migrations_preserve_legacy_scope_and_identity(
    tmp_path: Path, version: int
) -> None:
    path = tmp_path / "legacy.db"
    host_id, job_id = uuid4(), uuid4()
    now = datetime.now(UTC).isoformat()
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY)"
        )
        for index, migration in enumerate(_MIGRATIONS[:version], 1):
            connection.executescript(migration)
            connection.execute("INSERT INTO schema_migrations VALUES (?)", (index,))
        connection.execute(
            "INSERT INTO hosts(id,name,address,port,username,package_provider,"
            "created_at,updated_at) VALUES (?,?,?,22,?,'debian_apt',?,?)",
            (
                str(host_id),
                "Node 01",
                "node-01.example.invalid",
                "automation",
                now,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO jobs(id,action,host_id,state,created_at) "
            "VALUES (?,'update',?,'queued',?)",
            (str(job_id), str(host_id), now),
        )
        if version == 9:
            connection.execute("UPDATE jobs SET package_name='curl'")
    database = Database(path)
    await database.async_migrate()
    await database.async_migrate()
    host = await HostRepository(database).async_get(host_id)
    job = await JobRepository(database).async_get(job_id)
    assert host is not None
    assert host.id == host_id
    assert host.packages == ()
    assert job is not None
    assert job.id == job_id
    assert job.state is JobState.QUEUED
    assert job.package_names == ()
    assert job.package_name == ("curl" if version == 9 else None)


def test_empty_selection_cannot_fall_back_to_full_update() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        DebianAptProvider().selected_update_module(())
