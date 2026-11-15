"""Transactional SQLite adapter for the resource registry application port."""

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from ..contracts.resources import (
    HostResource,
    ManagedServiceResource,
    ProviderBinding,
    RelationshipKind,
    ResourceKind,
    ResourceRef,
    ResourceRelationship,
)
from ..persistence.sqlite import Database
from .entities import InfrastructureResource, RegistryConflict, RegistryResource

_SELECT = (
    "SELECT r.*,s.service_type,s.host_id FROM resources r "
    "LEFT JOIN managed_services s ON s.resource_id=r.id"
)


def _resource(row: sqlite3.Row) -> RegistryResource:
    resource_id = UUID(row["id"])
    kind = ResourceKind(row["kind"])
    if kind is ResourceKind.HOST:
        return HostResource(resource_id, row["name"])
    binding = ProviderBinding(
        row["provider_id"], UUID(row["connection_id"]), row["external_id"]
    )
    if kind is ResourceKind.MANAGED_SERVICE:
        host = (
            ResourceRef(ResourceKind.HOST, UUID(row["host_id"]))
            if row["host_id"]
            else None
        )
        return ManagedServiceResource(
            resource_id, row["name"], row["service_type"], binding, host
        )
    return InfrastructureResource(resource_id, row["name"], kind, binding)


def _get(connection: sqlite3.Connection, resource_id: UUID) -> RegistryResource | None:
    row = connection.execute(
        _SELECT + " WHERE r.id=? AND r.deleted_at IS NULL", (str(resource_id),)
    ).fetchone()
    return _resource(row) if row else None


def _require(connection: sqlite3.Connection, ref: ResourceRef) -> RegistryResource:
    resource = _get(connection, ref.id)
    if resource is None or resource.ref != ref:
        raise RegistryConflict("Resource is not available or has the wrong kind")
    return resource


def _insert(
    connection: sqlite3.Connection,
    resource: ManagedServiceResource | InfrastructureResource,
) -> None:
    now = datetime.now(UTC).isoformat()
    connection.execute(
        "INSERT INTO "
        "resources(id,kind,name,provider_id,connection_id,external_id,"
        "created_at,updated_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (
            str(resource.id),
            resource.ref.kind,
            resource.name,
            resource.binding.provider_id,
            str(resource.binding.connection_id),
            resource.binding.external_id,
            now,
            now,
        ),
    )


def _edge(connection: sqlite3.Connection, relation: ResourceRelationship) -> None:
    _require(connection, relation.source)
    target = _require(connection, relation.target)
    cyclic = connection.execute(
        "WITH RECURSIVE reachable(id) AS (SELECT target_id FROM "
        "resource_relationships WHERE source_id=? UNION SELECT "
        "e.target_id FROM resource_relationships e JOIN reachable p "
        "ON e.source_id=p.id) SELECT 1 FROM reachable WHERE id=?",
        (str(relation.target.id), str(relation.source.id)),
    ).fetchone()
    if cyclic:
        raise RegistryConflict("Resource relationship would create a cycle")
    if relation.kind is RelationshipKind.RUNS_SERVICE:
        assert isinstance(target, ManagedServiceResource)
        if target.host is not None and target.host != relation.source:
            raise RegistryConflict(
                "Service is already linked; use explicit reassignment"
            )
        connection.execute(
            "UPDATE managed_services SET host_id=? WHERE resource_id=?",
            (str(relation.source.id), str(relation.target.id)),
        )
    connection.execute(
        "INSERT OR IGNORE INTO "
        "resource_relationships(kind,source_id,target_id) "
        "VALUES(?,?,?)",
        (relation.kind, str(relation.source.id), str(relation.target.id)),
    )
    # OR IGNORE must not hide a different one-to-one reconciliation conflict.
    if (
        connection.execute(
            "SELECT 1 FROM resource_relationships WHERE kind=? AND "
            "source_id=? AND target_id=?",
            (relation.kind, str(relation.source.id), str(relation.target.id)),
        ).fetchone()
        is None
    ):
        raise RegistryConflict("Resource identity is already linked")


class SqliteResourceRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def _write[T](self, operation: Callable[[sqlite3.Connection], T]) -> T:
        try:
            return await self._database.async_transaction(operation)
        except sqlite3.IntegrityError:
            raise RegistryConflict(
                "Resource identity or binding already exists"
            ) from None

    async def async_list(self, limit: int, offset: int) -> tuple[RegistryResource, ...]:
        rows = await self._database.async_fetch_all(
            _SELECT
            + " WHERE r.deleted_at IS NULL ORDER BY r.name,r.id LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return tuple(_resource(row) for row in rows)

    async def async_get(self, resource_id: UUID) -> RegistryResource | None:
        row = await self._database.async_fetch_one(
            _SELECT + " WHERE r.id=? AND r.deleted_at IS NULL", (str(resource_id),)
        )
        return _resource(row) if row else None

    async def async_add_service(
        self, resource: ManagedServiceResource
    ) -> ManagedServiceResource:
        def write(connection: sqlite3.Connection) -> ManagedServiceResource:
            _insert(connection, resource)
            connection.execute(
                "INSERT INTO managed_services(resource_id,service_type) VALUES(?,?)",
                (str(resource.id), resource.service_type),
            )
            if resource.host:
                _edge(
                    connection,
                    ResourceRelationship(
                        RelationshipKind.RUNS_SERVICE, resource.host, resource.ref
                    ),
                )
            return resource

        return await self._write(write)

    async def async_reconcile_instance(
        self,
        name: str,
        kind: ResourceKind,
        binding: ProviderBinding,
        host_id: UUID | None,
    ) -> RegistryResource:
        def write(connection: sqlite3.Connection) -> RegistryResource:
            row = connection.execute(
                _SELECT + " WHERE r.provider_id=? AND r.connection_id=? AND "
                "r.external_id=? AND r.deleted_at IS NULL",
                (binding.provider_id, str(binding.connection_id), binding.external_id),
            ).fetchone()
            resource = (
                _resource(row)
                if row
                else InfrastructureResource(uuid4(), name, kind, binding)
            )
            if (
                not isinstance(resource, InfrastructureResource)
                or resource.kind != kind
            ):
                raise RegistryConflict("Binding belongs to another resource kind")
            if row is None:
                _insert(connection, resource)
            if host_id is not None:
                _edge(
                    connection,
                    ResourceRelationship(
                        RelationshipKind.CORRESPONDS_TO_HOST,
                        resource.ref,
                        ResourceRef(ResourceKind.HOST, host_id),
                    ),
                )
            return resource

        return await self._write(write)

    async def async_link_service(
        self, service_id: UUID, host_id: UUID | None
    ) -> RegistryResource:
        def write(connection: sqlite3.Connection) -> RegistryResource:
            resource = _require(
                connection, ResourceRef(ResourceKind.MANAGED_SERVICE, service_id)
            )
            connection.execute(
                "DELETE FROM resource_relationships WHERE kind='runs_service' "
                "AND target_id=?",
                (str(service_id),),
            )
            connection.execute(
                "UPDATE managed_services SET host_id=NULL WHERE resource_id=?",
                (str(service_id),),
            )
            if host_id is not None:
                _edge(
                    connection,
                    ResourceRelationship(
                        RelationshipKind.RUNS_SERVICE,
                        ResourceRef(ResourceKind.HOST, host_id),
                        resource.ref,
                    ),
                )
            result = _get(connection, service_id)
            assert result is not None
            return result

        return await self._write(write)

    async def async_relations(
        self, resource_id: UUID, limit: int, offset: int
    ) -> tuple[ResourceRelationship, ...]:
        rows = await self._database.async_fetch_all(
            "SELECT e.kind,e.source_id,e.target_id,s.kind AS "
            "source_kind,t.kind AS target_kind FROM "
            "resource_relationships e JOIN resources s ON "
            "s.id=e.source_id JOIN resources t ON t.id=e.target_id WHERE "
            "e.source_id=? OR e.target_id=? ORDER BY "
            "e.kind,e.source_id,e.target_id LIMIT ? OFFSET ?",
            (str(resource_id), str(resource_id), limit, offset),
        )
        return tuple(
            ResourceRelationship(
                RelationshipKind(row["kind"]),
                ResourceRef(ResourceKind(row["source_kind"]), UUID(row["source_id"])),
                ResourceRef(ResourceKind(row["target_kind"]), UUID(row["target_id"])),
            )
            for row in rows
        )

    async def async_add_relation(self, relation: ResourceRelationship) -> None:
        await self._write(lambda connection: _edge(connection, relation))

    async def async_remove_relation(self, relation: ResourceRelationship) -> bool:
        def write(connection: sqlite3.Connection) -> bool:
            _require(connection, relation.source)
            _require(connection, relation.target)
            changed = connection.execute(
                "DELETE FROM resource_relationships WHERE kind=? AND "
                "source_id=? AND target_id=?",
                (relation.kind, str(relation.source.id), str(relation.target.id)),
            ).rowcount
            if changed and relation.kind is RelationshipKind.RUNS_SERVICE:
                connection.execute(
                    "UPDATE managed_services SET host_id=NULL WHERE resource_id=?",
                    (str(relation.target.id),),
                )
            return bool(changed)

        return await self._write(write)

    async def async_remove(self, resource_id: UUID) -> bool:
        def write(connection: sqlite3.Connection) -> bool:
            resource = _get(connection, resource_id)
            if resource is None:
                return False
            if isinstance(resource, HostResource):
                raise RegistryConflict(
                    "Remove hosts through the existing host inventory"
                )
            connection.execute(
                "UPDATE resources SET deleted_at=? WHERE id=?",
                (datetime.now(UTC).isoformat(), str(resource_id)),
            )
            connection.execute(
                "DELETE FROM resource_relationships WHERE source_id=? OR target_id=?",
                (str(resource_id), str(resource_id)),
            )
            return True

        return await self._write(write)
