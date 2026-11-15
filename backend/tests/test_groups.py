"""Groups are metadata only, deterministic, bounded and authenticated."""

from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.homelab_backend.contracts.resources import (
    ProviderBinding,
    RelationshipKind,
    ResourceKind,
)
from backend.homelab_backend.groups.application import GroupService
from backend.homelab_backend.groups.entities import (
    Group,
    GroupConflict,
    Predicate,
    ResourceFacts,
    RuleField,
    SmartRule,
    matches,
)
from backend.homelab_backend.groups.repository import SqliteGroupStore
from backend.homelab_backend.groups.schemas import RuleData
from backend.homelab_backend.models import HostCreate
from backend.tests.test_backend_api import TOKEN, FakeExecutor, _client, _csrf
from backend.tests.test_resource_registry import setup_registry


def test_rules_exact_positive_known_facts_and_invalid_rules() -> None:
    host_id, related = uuid4(), uuid4()
    facts = ResourceFacts(
        host_id,
        ResourceKind.HOST,
        "Node",
        "Debian",
        frozenset({"security_updates"}),
        frozenset({"production"}),
        frozenset({"packages.update.full@1"}),
        frozenset({(RelationshipKind.RUNS_SERVICE, related)}),
    )
    predicates = [
        Predicate(RuleField.TYPE, "host"),
        Predicate(RuleField.DISTRO, "debian"),
        Predicate(RuleField.TAG, "production"),
        Predicate(RuleField.CAPABILITY, "packages.update.full@1"),
        Predicate(RuleField.STATUS, "security_updates"),
        Predicate(RuleField.RELATIONSHIP, str(related), RelationshipKind.RUNS_SERVICE),
    ]
    assert matches(SmartRule("all", tuple(predicates)), facts)
    unknown = ResourceFacts(host_id, ResourceKind.HOST, "Unknown")
    for predicate in predicates[1:]:
        assert not matches(SmartRule("all", (predicate,)), unknown)
    assert matches(SmartRule("any", tuple(predicates)), unknown)
    assert not matches(
        SmartRule("all", (Predicate(RuleField.TYPE, "container"),)), facts
    )
    assert not matches(
        SmartRule("all", (predicates[1],)), replace(facts, distro="Ubuntu")
    )
    for field, value, relation in [
        (RuleField.TAG, "Bad Tag", None),
        (RuleField.TYPE, "bogus", None),
        (RuleField.CAPABILITY, "packages.update.full", None),
        (RuleField.STATUS, "", None),
        (RuleField.STATUS, "x" * 129, None),
        (RuleField.DISTRO, "Debian", RelationshipKind.RUNS_SERVICE),
        (RuleField.RELATIONSHIP, "invalid", RelationshipKind.RUNS_SERVICE),
        (RuleField.RELATIONSHIP, str(related), None),
    ]:
        with pytest.raises(GroupConflict):
            Predicate(field, value, relation)
    for combine, items in [("eval", predicates), ("all", []), ("all", predicates * 3)]:
        with pytest.raises(GroupConflict):
            SmartRule(combine, tuple(items))
    for name, description, members, rule in [
        ("", "", (), None),
        ("x" * 101, "", (), None),
        ("ok", "x" * 501, (), None),
        ("ok", "", (host_id, host_id), None),
        ("ok", "", tuple(uuid4() for _ in range(501)), None),
        ("ok", "", (host_id,), SmartRule("all", (predicates[0],))),
    ]:
        with pytest.raises(GroupConflict):
            Group(uuid4(), name, description, rule, members)


async def test_persistence_multimembership_snapshot_and_fail_closed(
    tmp_path: Path,
) -> None:
    db, registry, hosts = await setup_registry(tmp_path)
    host = await hosts.async_create(
        HostCreate(
            name="Node", address="node-01.example.invalid", username="automation"
        )
    )
    linked = await registry.async_create_service(
        "Widget",
        "minecraft",
        ProviderBinding("synthetic.service", uuid4(), "service-01"),
        host.id,
    )
    store = SqliteGroupStore(db)
    service = GroupService(store)
    manual = Group(uuid4(), "Production", "", members=(host.id,))
    await service.async_save(manual, create=True)
    await service.async_save(
        Group(uuid4(), "Backup", "", members=(host.id, linked.id)), create=True
    )
    assert len(await service.async_list("", 25, 0)) == 2
    assert (await service.async_list("prod", 1, 0)) == (manual,)
    assert (await service.async_list("", 1, 1))[0].id == manual.id
    await service.async_tags(host.id, frozenset({"production"}))
    rule = SmartRule("all", (Predicate(RuleField.TAG, "production"),))
    smart = Group(uuid4(), "Tagged", "", rule)
    await service.async_save(smart, create=True)
    assert (await service.async_get(smart.id)) == smart
    assert len(await service.async_preview(rule)) == 1
    assert len(await service.async_preview(None, manual.members)) == 1
    before = await db.async_fetch_all("SELECT * FROM resource_groups")
    await service.async_preview(rule)
    assert [tuple(r) for r in before] == [
        tuple(r) for r in await db.async_fetch_all("SELECT * FROM resource_groups")
    ]
    for create, group in [
        (True, manual),
        (False, replace(manual, id=uuid4())),
        (True, replace(manual, id=uuid4(), members=(uuid4(),))),
    ]:
        with pytest.raises(GroupConflict):
            await service.async_save(group, create=create)
    await service.async_save(replace(manual, name="Renamed"), create=False)
    for tags in [frozenset({"Bad"}), frozenset(f"tag-{i}" for i in range(33))]:
        with pytest.raises(GroupConflict):
            await service.async_tags(host.id, tags)
    with pytest.raises(GroupConflict):
        await service.async_tags(uuid4(), frozenset())
    await db.async_execute(
        "UPDATE hosts SET checked_at=?,status='ok',distribution='Debian',"
        "updates=2,security_updates=1,reboot_required=1",
        ("2026-11-16T10:00:00+00:00",),
    )
    facts = (await store.async_snapshot())[0]
    assert facts.statuses == {
        "ok",
        "updates_pending",
        "security_updates",
        "restart_required",
    }
    assert facts.capabilities == frozenset()
    assert facts.relationships == {(RelationshipKind.RUNS_SERVICE, linked.id)}
    assert (await store.async_snapshot())[1].statuses == frozenset()
    await db.async_execute(
        "UPDATE resource_groups SET rule_json=? WHERE id=?",
        ('{"untrusted":"synthetic-private"}', str(smart.id)),
    )
    with pytest.raises(GroupConflict, match="Stored group is invalid"):
        await service.async_get(smart.id)
    await hosts.async_delete(host.id)
    assert await service.async_preview(None, manual.members) == ()
    assert await service.async_delete(smart.id)
    assert not await service.async_delete(smart.id)
    assert await service.async_get(smart.id) is None
    await db.async_migrate()
    assert (await service.async_get(manual.id)).members == (host.id,)
    fake = AsyncMock()
    fake.async_snapshot.return_value = (facts,) * 5001
    with pytest.raises(GroupConflict, match="bounded"):
        await GroupService(fake).async_preview(None)
    # Bound before materializing tags or edges, rather than returning a partial group.
    await db.async_transaction(
        lambda c: c.executemany(
            "INSERT INTO resources(id,kind,name,created_at,updated_at) "
            "VALUES(?,'host','Synthetic','','')",
            [(str(uuid4()),) for _ in range(5001)],
        )
    )
    with pytest.raises(GroupConflict, match="bounded"):
        await store.async_snapshot()


@pytest.mark.parametrize("ui", [False, True])
def test_api_preview_crud_tags_auth_and_no_execution(tmp_path: Path, ui: bool) -> None:
    executor = FakeExecutor()
    with _client(tmp_path, executor) as client:
        assert client.get("/api/v1/groups").status_code == 401
        csrf = _csrf(client)
        assert client.post("/ui-api/groups", json={}).status_code == 401
        client.post(
            "/ui-api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"api_token": TOKEN},
        )
        assert client.post("/ui-api/groups", json={}).status_code == 403
        base = "/ui-api" if ui else "/api/v1"
        headers = {"X-CSRF-Token": csrf} if ui else {"Authorization": f"Bearer {TOKEN}"}
        host = client.post(
            base + "/hosts",
            headers=headers,
            json={
                "name": "Node",
                "address": "node-01.example.invalid",
                "username": "automation",
            },
        ).json()
        resource_id = host["id"]
        assert (
            client.put(
                base + f"/resources/{resource_id}/tags",
                headers=headers,
                json={"tags": ["production"]},
            ).status_code
            == 204
        )
        assert (
            client.put(
                base + f"/resources/{uuid4()}/tags", headers=headers, json={"tags": []}
            ).status_code
            == 409
        )
        data = {"name": "Production", "kind": "manual", "members": [resource_id]}
        assert (
            client.post(base + "/groups/preview", headers=headers, json=data).json()[
                "total"
            ]
            == 1
        )
        assert client.get(base + "/groups", headers=headers).json() == []
        created = client.post(base + "/groups", headers=headers, json=data)
        assert created.status_code == 201
        group_id = created.json()["id"]
        assert client.get(base + f"/groups/{group_id}", headers=headers).json()[
            "members"
        ] == [resource_id]
        assert (
            client.get(
                base + f"/groups/{group_id}/resources?limit=1&offset=1", headers=headers
            ).json()["items"]
            == []
        )
        assert (
            client.get(
                base + "/group-resources?kind=host&tag=production&query=node",
                headers=headers,
            ).json()["total"]
            == 1
        )
        assert (
            client.get(
                base + "/group-resources?kind=container", headers=headers
            ).json()["total"]
            == 0
        )
        smart = {
            "name": "Smart",
            "kind": "smart",
            "rule": {
                "combine": "all",
                "predicates": [{"field": "tag", "value": "production"}],
            },
        }
        assert (
            client.put(
                base + f"/groups/{group_id}", headers=headers, json=smart
            ).status_code
            == 200
        )
        assert (
            client.get(base + f"/groups/{group_id}/resources", headers=headers).json()[
                "total"
            ]
            == 1
        )
        for bad in [
            {**smart, "rule": {"combine": "eval", "predicates": []}},
            {**smart, "members": [resource_id]},
            {**data, "members": [resource_id, resource_id]},
            {
                **smart,
                "rule": {
                    "predicates": [
                        {
                            "field": "tag",
                            "value": "production",
                            "script": "synthetic-private",
                        }
                    ]
                },
            },
        ]:
            result = client.post(base + "/groups/preview", headers=headers, json=bad)
            assert result.status_code == 422
            assert "synthetic-private" not in result.text
        assert (
            client.put(
                base + f"/groups/{uuid4()}", headers=headers, json=data
            ).status_code
            == 409
        )
        for suffix in ["", "/resources"]:
            assert (
                client.get(
                    base + f"/groups/{uuid4()}" + suffix, headers=headers
                ).status_code
                == 404
            )
        assert (
            client.get(base + "/groups?limit=101", headers=headers).status_code == 422
        )
        assert (
            client.delete(base + f"/groups/{group_id}", headers=headers).status_code
            == 204
        )
        assert (
            client.delete(base + f"/groups/{group_id}", headers=headers).status_code
            == 404
        )
        assert client.get(base + "/jobs", headers=headers).json() == []
        assert executor.calls == []


async def test_relationship_bound_and_additive_group_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sqlite3

    from backend.homelab_backend.database import _MIGRATIONS, Database
    from backend.homelab_backend.groups import repository as grouping
    from backend.homelab_backend.persistence import sqlite as storage

    db, registry, hosts = await setup_registry(tmp_path)
    host = await hosts.async_create(
        HostCreate(
            name="Node", address="node-01.example.invalid", username="automation"
        )
    )
    await registry.async_create_service(
        "Service",
        "minecraft",
        ProviderBinding("synthetic.service", uuid4(), "01"),
        host.id,
    )
    monkeypatch.setattr(grouping, "MAX_RELATIONSHIPS", 0)
    with pytest.raises(GroupConflict, match="Relationships"):
        await SqliteGroupStore(db).async_snapshot()
    before = [tuple(row) for row in await db.async_fetch_all("SELECT * FROM hosts")]
    monkeypatch.setattr(
        storage,
        "MIGRATIONS",
        (
            *_MIGRATIONS,
            (
                "CREATE TABLE group_probe(id INTEGER); "
                "INSERT INTO missing_group_probe VALUES(1);"
            ),
        ),
    )
    with pytest.raises(sqlite3.OperationalError):
        await db.async_migrate()
    assert (
        await db.async_fetch_one(
            "SELECT name FROM sqlite_master WHERE name='group_probe'"
        )
        is None
    )
    assert [
        tuple(row) for row in await db.async_fetch_all("SELECT * FROM hosts")
    ] == before
    await Database(tmp_path / "homelab_updates.db").async_fetch_all(
        "SELECT * FROM resource_groups"
    )


def test_rule_boundary_rejects_nested_or_inconsistent_groups() -> None:
    from pydantic import ValidationError

    from backend.homelab_backend.groups.schemas import GroupInput

    for data in [
        {
            "name": "Manual",
            "kind": "manual",
            "rule": {"predicates": [{"field": "type", "value": "host"}]},
        },
        {"name": "Smart", "kind": "smart"},
        {
            "name": "Smart",
            "kind": "smart",
            "rule": {"predicates": [{"field": "all", "value": "host"}]},
        },
        {"name": "Smart", "kind": "smart", "rule": {"predicates": []}},
    ]:
        with pytest.raises(ValidationError):
            GroupInput.model_validate(data)
    assert RuleData.model_validate({
        "predicates": [
            {
                "field": "relationship",
                "value": str(uuid4()),
                "relationship": "runs_service",
            }
        ]
    }).domain()
