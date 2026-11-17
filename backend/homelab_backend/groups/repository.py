"""SQLite grouping adapter; snapshots are bounded and transactionally coherent."""

import sqlite3
from uuid import UUID

from ..contracts.resources import RelationshipKind, ResourceKind
from ..persistence.sqlite import Database
from .entities import MAX_RESOURCES, Group, GroupConflict, ResourceFacts
from .schemas import RuleData

MAX_RELATIONSHIPS = 20000


def _group(connection: sqlite3.Connection, row: sqlite3.Row) -> Group:
    try:
        rule = (
            RuleData.model_validate_json(row["rule_json"]).domain()
            if row["rule_json"]
            else None
        )
        members = tuple(
            UUID(item[0])
            for item in connection.execute(
                "SELECT resource_id FROM group_members WHERE group_id=? "
                "ORDER BY resource_id",
                (row["id"],),
            )
        )
        return Group(UUID(row["id"]), row["name"], row["description"], rule, members)
    except ValueError:
        raise GroupConflict(
            "Stored group is invalid; no membership was resolved"
        ) from None


class SqliteGroupStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def async_list(
        self, query: str, limit: int, offset: int
    ) -> tuple[Group, ...]:
        def read(connection: sqlite3.Connection) -> tuple[Group, ...]:
            rows = connection.execute(
                "SELECT * FROM resource_groups WHERE instr(lower(name),lower(?))>0 "
                "ORDER BY lower(name),id LIMIT ? OFFSET ?",
                (query, limit, offset),
            )
            return tuple(_group(connection, row) for row in rows)

        return await self._database.async_transaction(read)

    async def async_get(self, group_id: UUID) -> Group | None:
        def read(connection: sqlite3.Connection) -> Group | None:
            row = connection.execute(
                "SELECT * FROM resource_groups WHERE id=?", (str(group_id),)
            ).fetchone()
            return _group(connection, row) if row else None

        return await self._database.async_transaction(read)

    async def async_save(self, group: Group, *, create: bool) -> None:
        def write(connection: sqlite3.Connection) -> None:
            exists = connection.execute(
                "SELECT 1 FROM resource_groups WHERE id=?", (str(group.id),)
            ).fetchone()
            if bool(exists) == create:
                raise GroupConflict("Group already exists or is no longer available")
            for resource_id in group.members:
                if not connection.execute(
                    "SELECT 1 FROM resources WHERE id=? AND deleted_at IS NULL",
                    (str(resource_id),),
                ).fetchone():
                    raise GroupConflict("Manual member is no longer available")
            rule = (
                RuleData.from_domain(group.rule).model_dump_json()
                if group.rule
                else None
            )
            connection.execute(
                "INSERT INTO resource_groups(id,name,description,rule_json) "
                "VALUES(?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name,"
                "description=excluded.description,rule_json=excluded.rule_json",
                (str(group.id), group.name, group.description, rule),
            )
            connection.execute(
                "DELETE FROM group_members WHERE group_id=?", (str(group.id),)
            )
            connection.executemany(
                "INSERT INTO group_members(group_id,resource_id) VALUES(?,?)",
                [(str(group.id), str(item)) for item in group.members],
            )

        await self._database.async_transaction(write)

    async def async_delete(self, group_id: UUID) -> bool:
        return bool(
            await self._database.async_execute(
                "DELETE FROM resource_groups WHERE id=?", (str(group_id),)
            )
        )

    async def async_tags(self, resource_id: UUID, tags: frozenset[str]) -> None:
        def write(connection: sqlite3.Connection) -> None:
            if not connection.execute(
                "SELECT 1 FROM resources WHERE id=? AND deleted_at IS NULL",
                (str(resource_id),),
            ).fetchone():
                raise GroupConflict("Resource is no longer available")
            connection.execute(
                "DELETE FROM resource_tags WHERE resource_id=?", (str(resource_id),)
            )
            connection.executemany(
                "INSERT INTO resource_tags(resource_id,tag) VALUES(?,?)",
                [(str(resource_id), tag) for tag in sorted(tags)],
            )

        await self._database.async_transaction(write)

    async def async_snapshot(self) -> tuple[ResourceFacts, ...]:
        def read(connection: sqlite3.Connection) -> tuple[ResourceFacts, ...]:
            rows = connection.execute(
                "SELECT r.id,r.kind,r.name,h.distribution,h.status,h.checked_at,"
                "h.updates,h.security_updates,h.reboot_required FROM resources r "
                "LEFT JOIN hosts h ON h.id=r.id WHERE r.deleted_at IS NULL "
                "ORDER BY lower(r.name),r.id LIMIT ?",
                (MAX_RESOURCES + 1,),
            ).fetchall()
            if len(rows) > MAX_RESOURCES:
                raise GroupConflict("Inventory exceeds the bounded preview limit")
            tags: dict[UUID, set[str]] = {}
            for item in connection.execute(
                "SELECT t.resource_id,t.tag FROM resource_tags t "
                "JOIN resources r ON r.id=t.resource_id WHERE r.deleted_at IS NULL"
            ):
                tags.setdefault(UUID(item[0]), set()).add(item[1])
            edges: dict[UUID, set[tuple[RelationshipKind, UUID]]] = {}
            relationships = connection.execute(
                "SELECT kind,source_id,target_id FROM resource_relationships LIMIT ?",
                (MAX_RELATIONSHIPS + 1,),
            ).fetchall()
            if len(relationships) > MAX_RELATIONSHIPS:
                raise GroupConflict("Relationships exceed the bounded preview limit")
            for item in relationships:
                # Match incident edges to an explicit resource reference.
                source, target = UUID(item[1]), UUID(item[2])
                edges.setdefault(source, set()).add((RelationshipKind(item[0]), target))
                edges.setdefault(target, set()).add((RelationshipKind(item[0]), source))
            result = []
            for row in rows:
                statuses: set[str] = set()
                if row["checked_at"]:
                    if row["status"]:
                        statuses.add(row["status"])
                    if row["updates"]:
                        statuses.add("updates_pending")
                    if row["security_updates"]:
                        statuses.add("security_updates")
                    if row["reboot_required"]:
                        statuses.add("restart_required")
                resource_id = UUID(row["id"])
                result.append(
                    ResourceFacts(
                        resource_id,
                        ResourceKind(row["kind"]),
                        row["name"],
                        row["distribution"],
                        frozenset(statuses),
                        frozenset(tags.get(resource_id, ())),
                        relationships=frozenset(edges.get(resource_id, ())),
                    )
                )
            return tuple(result)

        return await self._database.async_transaction(read)
