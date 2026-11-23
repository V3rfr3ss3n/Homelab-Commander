"""Only configuration/counts persist; native package rows remain disposable."""

import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from backend.homelab_backend.app import create_app
from backend.homelab_backend.config import Settings
from backend.homelab_backend.database import _MIGRATIONS, Database
from backend.homelab_backend.execution.targets import connection_revision
from backend.homelab_backend.hosts import HostBusyError, HostRepository
from backend.homelab_backend.jobs import JobRepository
from backend.homelab_backend.models import HostCreate, HostPatch, JobAction
from backend.tests.test_backend_api import AUTH, TOKEN, _terminal_job
from backend.tests.test_package_sources import SourcesRunner
from backend.tests.test_rpm_persistence import old_database
from backend.tests.test_rpm_providers import executor


def test_native_rows_never_persist_and_partial_update_recovers_from_manager(tmp_path):
    runner = SourcesRunner()
    settings = Settings(data_dir=tmp_path, api_token=TOKEN)

    def application():
        return create_app(settings, executor=executor(tmp_path, runner))

    with TestClient(application()) as client:
        host = client.post(
            "/api/v1/hosts",
            headers=AUTH,
            json={
                "name": "Synthetic",
                "address": "node-01.example.invalid",
                "username": "automation",
                "package_provider": "auto",
            },
        ).json()
        root = "/api/v1/hosts/" + host["id"]
        checked = client.post(root + "/actions/check-updates", headers=AUTH).json()
        assert _terminal_job(client, checked["id"])["state"] == "success"
        packages = client.get(root + "/packages", headers=AUTH).json()
        assert packages["total"] == 6
        assert len(packages["packages"]) == 6
        assert len(packages["sources"]) == 3
        with closing(sqlite3.connect(settings.database_path)) as connection:
            assert (
                connection.execute("SELECT packages_json FROM hosts").fetchone()[0]
                == "[]"
            )
            assert not any(
                "package" in row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            )
        runner.flatpak_fail = "system"
        updated = client.post(root + "/actions/update", headers=AUTH).json()
        failed = _terminal_job(client, updated["id"])
        assert failed["state"] == "failed"
        assert failed["needs_review"]
        assert failed["error_code"] == "package_sources_partial_failure"
        stale = client.get(root, headers=AUTH).json()
        assert stale["updates"] == 6
        assert stale["status"] == "stale"
        checked = client.post(root + "/actions/check-updates", headers=AUTH).json()
        assert _terminal_job(client, checked["id"])["state"] == "success"
        packages = client.get(root + "/packages", headers=AUTH).json()
        assert packages["total"] == 4
        assert len(packages["packages"]) == 4
    # A new application process does not reload a package-to-manager catalog.
    with TestClient(application()) as client:
        packages = client.get(root + "/packages", headers=AUTH).json()
        assert packages["total"] == 4
        assert packages["packages"] == []
        checked = client.post(root + "/actions/check-updates", headers=AUTH).json()
        assert _terminal_job(client, checked["id"])["state"] == "success"
        assert len(client.get(root + "/packages", headers=AUTH).json()["packages"]) == 4


async def test_source_configuration_roundtrip_resets_and_busy_guards(tmp_path):
    db = Database(tmp_path / "data.db")
    await db.async_migrate()
    hosts = HostRepository(db)
    host = await hosts.async_create(
        HostCreate(
            name="Synthetic",
            address="node-01.example.invalid",
            username="automation",
            package_provider="auto",
        )
    )
    legacy = await db.async_transaction(lambda conn: connection_revision(conn, host.id))
    updated = await hosts.async_patch(
        host.id, HostPatch(package_sources=("flatpak_user",))
    )
    assert updated.package_sources == ("flatpak_user",)
    assert updated.checked_at is None
    assert updated.id == host.id
    assert (await hosts.async_get(host.id)).package_sources == ("flatpak_user",)
    assert (
        await db.async_transaction(lambda conn: connection_revision(conn, host.id))
        != legacy
    )
    reset = await hosts.async_patch(host.id, HostPatch(package_sources=None))
    assert reset.package_sources is None
    assert (
        await db.async_transaction(lambda conn: connection_revision(conn, host.id))
        == legacy
    )
    repository = JobRepository(db)
    job = await repository.async_create(
        JobAction.UPDATE, host.id, package_name="source::flatpak_user"
    )
    assert job.execution.scope.package_name == "source::flatpak_user"
    assert await repository.async_claim(job.id)
    with pytest.raises(HostBusyError):
        await hosts.async_patch(host.id, HostPatch(package_sources=("system",)))
    with pytest.raises(sqlite3.IntegrityError, match="host_execution_busy"):
        await db.async_execute(
            "UPDATE hosts SET package_sources_json='[\"system\"]' WHERE id=?",
            (str(host.id),),
        )


async def test_schema_16_is_additive_and_rollback_is_atomic(tmp_path, monkeypatch):
    path = tmp_path / "migration.db"
    identity = old_database(path)
    # Materialize the genuine schema-15 state before attempting the next migration.
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(_MIGRATIONS[14])
        connection.execute("INSERT INTO schema_migrations VALUES (15)")
        connection.commit()
    from backend.homelab_backend.persistence import sqlite as adapter

    monkeypatch.setattr(
        adapter, "MIGRATIONS", (*_MIGRATIONS[:15], _MIGRATIONS[15] + "INVALID SQL;")
    )
    with pytest.raises(sqlite3.OperationalError):
        await Database(path).async_migrate()
    with closing(sqlite3.connect(path)) as connection:
        assert (
            connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[
                0
            ]
            == 15
        )
        assert "package_sources_json" not in {
            r[1] for r in connection.execute("PRAGMA table_info(hosts)")
        }
    monkeypatch.setattr(adapter, "MIGRATIONS", _MIGRATIONS)
    await Database(path).async_migrate()
    host = await HostRepository(Database(path)).async_get(identity)
    assert str(host.id) == str(identity)
    assert host.updates == 7
    assert host.package_sources is None
    assert host.package_observations == ()
    assert host.security_updates == 2
    assert host.reboot_required


async def test_queued_source_change_fails_before_any_native_work(tmp_path):
    from backend.homelab_backend.custom_tasks import CustomTaskRepository
    from backend.homelab_backend.jobs import JobManager

    db = Database(tmp_path / "queued.db")
    await db.async_migrate()
    hosts = HostRepository(db)
    host = await hosts.async_create(
        HostCreate(
            name="Synthetic",
            address="node-01.example.invalid",
            username="automation",
            package_provider="auto",
        )
    )
    runner = SourcesRunner()
    repository = JobRepository(db)
    manager = JobManager(
        repository,
        hosts,
        CustomTaskRepository(db, allow_shell=False),
        executor(tmp_path, runner),
    )
    job = await manager.async_enqueue(JobAction.UPDATE, host.id, "source::flatpak_user")
    await hosts.async_patch(host.id, HostPatch(package_sources=("system",)))
    await manager.async_start()
    try:
        await manager.async_wait_idle()
        changed = await repository.async_get(job.id)
        assert changed.error_code == "execution_scope_changed"
        assert not runner.native_calls
        assert runner.writes == 0
    finally:
        await manager.async_stop()


async def test_upgrade_preserves_legacy_bytes_and_refresh_hides_old_rows(
    tmp_path,
):
    import json
    from datetime import UTC, datetime

    path = tmp_path / "legacy-cache.db"
    identity = old_database(path)
    cached = json.dumps([
        {
            "name": "legacy-cache-only",
            "old_version": "1",
            "new_version": "2",
            "is_security": False,
        }
    ])
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("UPDATE hosts SET packages_json=?", (cached,))
        connection.commit()
    db = Database(path)
    await db.async_migrate()
    before = await db.async_fetch_one("SELECT packages_json FROM hosts")
    assert before["packages_json"] == cached
    hosts = HostRepository(db)
    host = await hosts.async_get(identity)
    assert host.packages[0].name == "legacy-cache-only"
    await hosts.async_update_status(
        host.id,
        distribution="Debian",
        distribution_version="12",
        kernel="synthetic",
        updates=7,
        security_updates=2,
        reboot_required=True,
        status="ok",
        checked_at=datetime.now(UTC),
        packages=(),
    )
    after = await db.async_fetch_one("SELECT packages_json FROM hosts")
    assert after["packages_json"] == cached
    assert (await hosts.async_get(host.id)).packages == ()
    assert (await HostRepository(db).async_get(host.id)).packages == ()
