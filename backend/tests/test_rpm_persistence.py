"""Native-provider API/cache and additive migration tests, synthetic data only."""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.homelab_backend.app import create_app
from backend.homelab_backend.config import Settings
from backend.homelab_backend.database import _MIGRATIONS, Database
from backend.homelab_backend.hosts import HostRepository
from backend.homelab_backend.models import HostPatch
from backend.tests.test_backend_api import AUTH, TOKEN, _terminal_job
from backend.tests.test_rpm_providers import RpmRunner, executor


@pytest.mark.parametrize("provider", ["dnf", "zypper"])
def test_api_unknown_data_and_failed_transaction_preserve_cache(tmp_path, provider):
    runner = (
        RpmRunner()
        if provider == "dnf"
        else RpmRunner("openSUSE Leap", "16.0", "zypper")
    )
    with TestClient(
        create_app(
            Settings(data_dir=tmp_path, api_token=TOKEN),
            executor=executor(tmp_path, runner),
        )
    ) as client:
        created = client.post(
            "/api/v1/hosts",
            headers=AUTH,
            json={
                "name": "Synthetic RPM node",
                "address": "rpm-node.example.invalid",
                "username": "automation",
                "package_provider": provider,
            },
        )
        assert created.status_code == 201
        host_id = created.json()["id"]
        assert created.json()["security_updates"] is None
        assert created.json()["reboot_required"] is None
        check = client.post(
            f"/api/v1/hosts/{host_id}/actions/check-updates", headers=AUTH
        )
        assert _terminal_job(client, check.json()["id"])["state"] == "success"
        before = client.get(f"/api/v1/hosts/{host_id}", headers=AUTH).json()
        assert before["updates"] == 2
        assert before["security_updates"] is None
        assert before["reboot_required"] is (False if provider == "zypper" else None)
        assert before["package_scopes"] == ["full", "selected", "single"]
        package = client.get(f"/api/v1/hosts/{host_id}/packages", headers=AUTH).json()
        assert package["security_updates"] is None
        assert package["total"] == 2
        assert package["packages"][0]["is_security"] is None
        runner.update_rc = 1
        update = client.post(
            f"/api/v1/hosts/{host_id}/actions/update",
            headers=AUTH,
            json={"package_name": "curl.x86_64"},
        )
        failed = _terminal_job(client, update.json()["id"])
        assert failed["state"] == "failed"
        assert failed["needs_review"]
        assert failed["error_code"] == "update_packages_failed"
        assert runner.writes == 1
        after = client.get(f"/api/v1/hosts/{host_id}", headers=AUTH).json()
        assert after["id"] == host_id
        assert after["updates"] == before["updates"]
        assert after["security_updates"] is None
        assert after["status"] == "stale"
        assert not any("rollback" in args or "undo" in args for args in runner.commands)
        recovered = client.post(
            f"/api/v1/hosts/{host_id}/actions/check-updates", headers=AUTH
        )
        assert _terminal_job(client, recovered.json()["id"])["state"] == "success"
        after = client.get(f"/api/v1/hosts/{host_id}", headers=AUTH).json()
        assert after["updates"] == 1
        assert after["security_updates"] is None
        assert after["status"] == "ok"


def old_database(path):
    identity = str(uuid4())
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            "CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY)"
        )
        for version, migration in enumerate(_MIGRATIONS[:14], 1):
            connection.executescript(migration)
            connection.execute("INSERT INTO schema_migrations VALUES (?)", (version,))
        stamp = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
        connection.execute(
            "INSERT INTO hosts(id,name,address,port,username,package_provider,"
            "created_at,updated_at,updates,security_updates,reboot_required) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                identity,
                "Synthetic node",
                "old-node.example.invalid",
                22,
                "automation",
                "debian_apt",
                stamp,
                stamp,
                7,
                2,
                1,
            ),
        )
        connection.commit()
    return identity


async def test_schema_15_preserves_legacy_identity_and_unknown_bits(tmp_path):
    path = tmp_path / "legacy.db"
    identity = old_database(path)
    database = Database(path)
    await database.async_migrate()
    hosts = HostRepository(database)
    host = (await hosts.async_list())[0]
    assert str(host.id) == identity
    assert host.updates == 7
    assert host.security_updates == 2
    assert host.reboot_required is True
    assert host.package_scopes is None
    await hosts.async_update_status(
        host.id,
        distribution="Fedora",
        distribution_version="45",
        kernel="synthetic",
        updates=3,
        security_updates=None,
        reboot_required=None,
        status="ok",
        checked_at=datetime.now(UTC),
        packages=(),
        package_scopes=("full",),
    )
    row = await database.async_fetch_one("SELECT * FROM hosts WHERE id=?", (identity,))
    assert row["security_known"] == row["reboot_known"] == 0
    same = await hosts.async_get(host.id)
    assert same.security_updates is None
    assert same.reboot_required is None
    assert same.updates == 3
    assert same.package_scopes == ("full",)
    await hosts.async_patch(host.id, HostPatch(package_provider="zypper"))
    changed = await hosts.async_get(host.id)
    assert changed.id == host.id
    assert changed.checked_at is None
    assert changed.security_updates is None
    assert changed.reboot_required is None
    assert changed.packages == ()
    assert changed.package_scopes == ()


async def test_schema_15_failure_rolls_back_all_new_columns(tmp_path, monkeypatch):
    path = tmp_path / "rollback.db"
    old_database(path)
    from backend.homelab_backend.persistence import sqlite as adapter

    monkeypatch.setattr(
        adapter, "MIGRATIONS", (*_MIGRATIONS[:14], _MIGRATIONS[14] + "INVALID SQL;")
    )
    with pytest.raises(sqlite3.OperationalError):
        await Database(path).async_migrate()
    with closing(sqlite3.connect(path)) as connection:
        assert (
            connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[
                0
            ]
            == 14
        )
        columns = {r[1] for r in connection.execute("PRAGMA table_info(hosts)")}
        assert not columns & {"security_known", "reboot_known", "package_scopes_json"}
        assert connection.execute(
            "SELECT updates,security_updates,reboot_required FROM hosts"
        ).fetchone() == (7, 2, 1)
