"""Registry transactions, legacy migration and authenticated admin API contracts."""

import asyncio
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from backend.homelab_backend.contracts.resources import (
    ProviderBinding,
    RelationshipKind,
    ResourceKind,
    ResourceRef,
    ResourceRelationship,
)
from backend.homelab_backend.database import _MIGRATIONS, Database
from backend.homelab_backend.hosts import DuplicateHostError, HostRepository
from backend.homelab_backend.models import HostCreate, HostPatch
from backend.homelab_backend.resources.application import ResourceRegistry
from backend.homelab_backend.resources.entities import (
    InfrastructureResource,
    RegistryConflict,
)
from backend.homelab_backend.resources.repository import SqliteResourceRepository
from backend.tests.test_backend_api import AUTH, FakeExecutor, _client, _csrf, _ui_login


def binding(external: str = "demo_server_01") -> ProviderBinding:
    return ProviderBinding(
        "test.platform", UUID("00000000-0000-4000-8000-000000000003"), external
    )


async def setup_registry(
    tmp_path: Path,
) -> tuple[Database, ResourceRegistry, HostRepository]:
    database = Database(tmp_path / "homelab_updates.db")
    await database.async_migrate()
    return (
        database,
        ResourceRegistry(SqliteResourceRepository(database)),
        HostRepository(database),
    )


async def test_service_lifecycle_host_facade_and_tombstones(tmp_path: Path) -> None:
    database, registry, hosts = await setup_registry(tmp_path)
    host = await hosts.async_create(
        HostCreate(
            name="Node 01", address="node-01.example.invalid", username="automation"
        )
    )
    second = await hosts.async_create(
        HostCreate(
            name="Node 02", address="node-02.example.invalid", username="automation"
        )
    )
    service = await registry.async_create_service(
        " Demo Minecraft ", "minecraft", binding()
    )
    assert service.host is None
    assert service.name == "Demo Minecraft"
    assert (await registry.async_get(host.id)).ref.id == host.id
    assert len(await registry.async_list()) == 3
    assert len(await registry.async_list(1, 1)) == 1
    linked = await registry.async_link_service(service.id, host.id)
    assert linked.host.id == host.id
    relation = (await registry.async_relations(service.id))[0]
    await registry.async_add_relation(relation)  # idempotent
    assert len(await registry.async_relations(service.id)) == 1
    assert await registry.async_relations(service.id, 1, 0) == (relation,)
    assert await registry.async_relations(service.id, 1, 1) == ()
    with pytest.raises(RegistryConflict, match="already linked"):
        await registry.async_add_relation(
            ResourceRelationship(
                RelationshipKind.RUNS_SERVICE,
                ResourceRef(ResourceKind.HOST, second.id),
                service.ref,
            )
        )
    with pytest.raises(RegistryConflict, match="not available"):
        await registry.async_link_service(service.id, uuid4())
    assert (await registry.async_get(service.id)).host.id == host.id
    assert await registry.async_remove_relation(relation)
    assert not await registry.async_remove_relation(relation)
    assert (await registry.async_get(service.id)).host is None
    await registry.async_link_service(service.id, second.id)
    await registry.async_link_service(service.id, None)
    await registry.async_link_service(service.id, host.id)
    await hosts.async_patch(host.id, HostPatch(name="Renamed"))
    assert (await registry.async_get(host.id)).name == "Renamed"
    await hosts.async_delete(host.id)
    assert await registry.async_get(host.id) is None
    assert (await registry.async_get(service.id)).host is None
    assert await registry.async_relations(service.id) == ()
    tombstone = await database.async_fetch_one(
        "SELECT deleted_at FROM resources WHERE id=?", (str(host.id),)
    )
    assert tombstone["deleted_at"] is not None
    with pytest.raises(RegistryConflict, match="host inventory"):
        await registry.async_remove(second.id)
    assert await registry.async_remove(service.id)
    assert not await registry.async_remove(service.id)
    assert await registry.async_get(service.id) is None
    replacement = await registry.async_create_service(
        "Replacement", "minecraft", binding()
    )
    assert replacement.id != service.id
    for limit, offset in [(0, 0), (101, 0), (1, -1)]:
        with pytest.raises(RegistryConflict, match="page"):
            await registry.async_list(limit, offset)
        with pytest.raises(RegistryConflict, match="page"):
            await registry.async_relations(service.id, limit, offset)
    for name in ["", "x" * 101]:
        with pytest.raises(RegistryConflict, match="name"):
            await registry.async_create_service(name, "minecraft", binding())


async def test_reconciliation_cycles_atomic_failures_and_uniqueness(
    tmp_path: Path,
) -> None:
    database, registry, hosts = await setup_registry(tmp_path)
    host = await hosts.async_create(
        HostCreate(
            name="Node 01", address="node-01.example.invalid", username="automation"
        )
    )
    vm = await registry.async_reconcile_instance(
        "VM 01", ResourceKind.VIRTUAL_MACHINE, binding("vm01"), host.id
    )
    again = await registry.async_reconcile_instance(
        "Other label", ResourceKind.VIRTUAL_MACHINE, binding("vm01")
    )
    assert vm.id == again.id
    assert len(await hosts.async_list()) == 1
    with pytest.raises(RegistryConflict, match="another resource kind"):
        await registry.async_reconcile_instance(
            "VM", ResourceKind.CONTAINER, binding("vm01")
        )
    with pytest.raises(RegistryConflict, match="already linked"):
        await registry.async_reconcile_instance(
            "VM 02", ResourceKind.VIRTUAL_MACHINE, binding("vm02"), host.id
        )
    assert len(await registry.async_list()) == 2  # failed identity rolled back
    platform = await registry.async_create_service(
        "Platform", "platform", binding("platform")
    )
    with pytest.raises(RegistryConflict, match="another resource kind"):
        await registry.async_reconcile_instance(
            "Bad", ResourceKind.CONTAINER, binding("platform")
        )
    first = ResourceRelationship(RelationshipKind.MANAGED_BY, vm.ref, platform.ref)
    await registry.async_add_relation(first)
    b = await registry.async_create_service("Other", "platform", binding("other"))
    await registry.async_add_relation(
        ResourceRelationship(RelationshipKind.MANAGED_BY, platform.ref, b.ref)
    )
    with pytest.raises(RegistryConflict, match="cycle"):
        await registry.async_add_relation(
            ResourceRelationship(RelationshipKind.MANAGED_BY, b.ref, platform.ref)
        )
    with pytest.raises(RegistryConflict, match="wrong kind"):
        await registry.async_add_relation(
            ResourceRelationship(
                RelationshipKind.MANAGED_BY,
                ResourceRef(ResourceKind.MANAGED_SERVICE, host.id),
                b.ref,
            )
        )
    with pytest.raises(RegistryConflict, match="binding already exists"):
        await registry.async_create_service(
            "Duplicate", "platform", binding("platform")
        )
    with pytest.raises(RegistryConflict, match="not available"):
        await registry.async_create_service(
            "Missing host", "minecraft", binding("missing"), uuid4()
        )
    assert len(await registry.async_list()) == 4
    assert await registry.async_remove(vm.id)
    assert await registry.async_relations(vm.id) == ()
    with pytest.raises(ValueError, match="infrastructure"):
        InfrastructureResource(uuid4(), "Invalid", ResourceKind.HOST, binding())
    with pytest.raises(ValueError, match="identities"):
        InfrastructureResource(
            binding().connection_id, "Invalid", ResourceKind.CONTAINER, binding()
        )
    # Host inserts are atomic with registry identity creation, including collision.
    await database.async_execute(
        "CREATE TRIGGER reject_registry BEFORE INSERT ON resources "
        "BEGIN SELECT RAISE(ABORT,'synthetic'); END;"
    )
    with pytest.raises(DuplicateHostError, match="already exists"):
        await hosts.async_create(
            HostCreate(
                name="Node 02", address="node-02.example.invalid", username="automation"
            )
        )
    assert len(await hosts.async_list()) == 1


def legacy_database(tmp_path: Path) -> Database:
    path = tmp_path / "homelab_updates.db"
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY)"
        )
        for version, migration in enumerate(_MIGRATIONS[:10], 1):
            connection.executescript(migration)
            connection.execute("INSERT INTO schema_migrations VALUES(?)", (version,))
        now = datetime.now(UTC).isoformat()
        connection.execute(
            "INSERT INTO hosts(id,name,address,port,username,package_provider,"
            "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (
                "00000000-0000-4000-8000-000000000001",
                "Node 01",
                "node-01.example.invalid",
                22,
                "automation",
                "debian_apt",
                now,
                now,
            ),
        )
        for state in ["queued", "running", "failed"]:
            job_id = str(uuid4())
            connection.execute(
                "INSERT INTO jobs(id,action,host_id,state,created_at,reviewed_at,"
                "package_names_json) VALUES(?,?,?,?,?,?,?)",
                (
                    job_id,
                    "update",
                    "00000000-0000-4000-8000-000000000001",
                    state,
                    now,
                    now if state == "failed" else None,
                    '["curl","vim"]',
                ),
            )
            connection.execute(
                "INSERT INTO job_logs(job_id,output,truncated) VALUES(?,?,?)",
                (job_id, "Synthetic preserved output", 0),
            )
        connection.execute(
            "INSERT INTO custom_tasks(id,name,description,mode,argv_json,"
            "enabled,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (str(uuid4()), "Task", "Synthetic", "command", '["uptime"]', 1, now, now),
        )
    for name in ["id_ed25519", "id_ed25519.pub", "known_hosts"]:
        (tmp_path / name).write_bytes(b"synthetic-identity-bytes-not-a-real-key")
    return Database(path)


async def test_dev5_backfill_is_additive_restart_safe_and_rollback_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = legacy_database(tmp_path)
    tables = ["hosts", "jobs", "custom_tasks", "job_logs"]
    original_columns = {
        table: [
            row["name"]
            for row in await database.async_fetch_all(
                "PRAGMA table_info(" + table + ")"
            )
        ]
        for table in tables
    }
    before = {
        table: [
            tuple(row[column] for column in original_columns[table])
            for row in await database.async_fetch_all("SELECT * FROM " + table)
        ]
        for table in tables
    }
    from backend.homelab_backend.persistence import sqlite as storage

    monkeypatch.setattr(
        storage,
        "MIGRATIONS",
        (*_MIGRATIONS[:10], _MIGRATIONS[10] + "\nINSERT INTO missing_table VALUES(1);"),
    )
    with pytest.raises(sqlite3.OperationalError, match="missing_table"):
        await database.async_migrate()
    assert (
        await database.async_fetch_one(
            "SELECT name FROM sqlite_master WHERE name='resources'"
        )
        is None
    )
    assert (
        await database.async_fetch_one(
            "SELECT MAX(version) AS v FROM schema_migrations"
        )
    )["v"] == 10
    monkeypatch.setattr(storage, "MIGRATIONS", _MIGRATIONS)
    await database.async_migrate()
    await database.async_migrate()
    assert before == {
        table: [
            tuple(row[column] for column in original_columns[table])
            for row in await database.async_fetch_all("SELECT * FROM " + table)
        ]
        for table in tables
    }
    assert (await database.async_fetch_one("SELECT COUNT(*) AS n FROM resources"))[
        "n"
    ] == 1
    for name in ["id_ed25519", "id_ed25519.pub", "known_hosts"]:
        assert (
            tmp_path / name
        ).read_bytes() == b"synthetic-identity-bytes-not-a-real-key"
    # Separate startup objects must not race the version check/backfill.
    await asyncio.gather(
        Database(tmp_path / "homelab_updates.db").async_migrate(),
        Database(tmp_path / "homelab_updates.db").async_migrate(),
    )


@pytest.mark.parametrize("ui", [False, True])
def test_registry_api_auth_validation_links_and_no_execution(
    tmp_path: Path, ui: bool
) -> None:
    executor = FakeExecutor()
    with _client(tmp_path, executor) as client:
        assert client.get("/api/v1/resources").status_code == 401
        csrf = _csrf(client)
        assert client.get("/ui-api/resources", headers=AUTH).status_code == 401
        if ui:
            _ui_login(client, csrf)
        base = "/ui-api" if ui else "/api/v1"
        headers = {"X-CSRF-Token": csrf} if ui else AUTH
        payload = {
            "name": "Demo Minecraft",
            "service_type": "minecraft",
            "binding": {
                "provider_id": "test.platform",
                "connection_id": str(binding().connection_id),
                "external_id": "demo_server_01",
            },
        }
        if ui:
            assert (
                client.post(base + "/resources/services", json=payload).status_code
                == 403
            )
        created = client.post(
            base + "/resources/services", headers=headers, json=payload
        )
        assert created.status_code == 201
        service = created.json()
        assert service["host_id"] is None
        assert (
            client.get(base + "/resources", headers=headers).json()[0]["id"]
            == service["id"]
        )
        assert (
            client.get(base + "/resources/" + service["id"], headers=headers).json()
            == service
        )
        assert (
            client.post(
                base + "/resources/services", headers=headers, json=payload
            ).status_code
            == 409
        )
        assert (
            client.post(
                base + "/resources/services",
                headers=headers,
                json={**payload, "token": "synthetic-secret"},
            ).status_code
            == 422
        )
        missing = str(uuid4())
        assert (
            client.get(base + "/resources/" + missing, headers=headers).status_code
            == 404
        )
        assert (
            client.get(
                base + "/resources/" + missing + "/relationships", headers=headers
            ).status_code
            == 404
        )
        assert (
            client.get(base + "/resources?limit=101", headers=headers).status_code
            == 422
        )
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
            client.get(base + "/resources/" + host["id"], headers=headers).json()[
                "binding"
            ]
            is None
        )
        linked = client.patch(
            base + "/resources/" + service["id"] + "/host",
            headers=headers,
            json={"host_id": host["id"]},
        )
        assert linked.status_code == 200
        edge = client.get(
            base + "/resources/" + service["id"] + "/relationships", headers=headers
        ).json()[0]
        assert (
            client.post(
                base + "/resource-relationships", headers=headers, json=edge
            ).status_code
            == 200
        )
        assert (
            client.request(
                "DELETE", base + "/resource-relationships", headers=headers, json=edge
            ).status_code
            == 204
        )
        assert (
            client.request(
                "DELETE", base + "/resource-relationships", headers=headers, json=edge
            ).status_code
            == 404
        )
        bad = {**edge, "source": edge["target"], "target": edge["source"]}
        assert (
            client.post(
                base + "/resource-relationships", headers=headers, json=bad
            ).status_code
            == 409
        )
        assert (
            client.request(
                "DELETE", base + "/resource-relationships", headers=headers, json=bad
            ).status_code
            == 409
        )
        instance = client.post(
            base + "/resources/instances",
            headers=headers,
            json={
                "name": "VM 01",
                "kind": "virtual_machine",
                "binding": {**payload["binding"], "external_id": "vm01"},
                "host_id": host["id"],
            },
        )
        assert instance.status_code == 200
        assert instance.json()["kind"] == "virtual_machine"
        assert (
            client.delete(
                base + "/resources/" + host["id"], headers=headers
            ).status_code
            == 409
        )
        assert (
            client.delete(
                base + "/resources/" + service["id"], headers=headers
            ).status_code
            == 204
        )
        assert (
            client.delete(
                base + "/resources/" + service["id"], headers=headers
            ).status_code
            == 404
        )
        assert (
            client.delete(base + "/resources/" + missing, headers=headers).status_code
            == 404
        )
        assert executor.calls == []


async def test_fresh_concurrent_startup_and_trailing_migration_statement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.homelab_backend.persistence import sqlite as storage

    monkeypatch.setattr(
        storage, "MIGRATIONS", (*_MIGRATIONS, "CREATE TABLE trailing_probe(id INTEGER)")
    )
    databases = [Database(tmp_path / "fresh.db"), Database(tmp_path / "fresh.db")]
    await asyncio.gather(*(database.async_migrate() for database in databases))
    assert (
        await databases[0].async_fetch_one(
            "SELECT COUNT(*) AS n FROM schema_migrations"
        )
    )["n"] == len(_MIGRATIONS) + 1
