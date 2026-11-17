"""Resource use cases depend on a persistence port, never on SQLite or HTTP."""

from typing import Protocol
from uuid import UUID, uuid4

from ..contracts.resources import (
    ManagedServiceResource,
    ProviderBinding,
    ResourceKind,
    ResourceRef,
    ResourceRelationship,
)
from ..policy.application import PolicyGuard
from ..policy.domain import Permission
from .entities import RegistryConflict, RegistryResource


class ResourceStore(Protocol):
    async def async_list(self, limit: int, offset: int) -> tuple[RegistryResource, ...]:
        """Read a bounded page of active resources."""

    async def async_get(self, resource_id: UUID) -> RegistryResource | None:
        """Read an active resource."""

    async def async_add_service(
        self, resource: ManagedServiceResource
    ) -> ManagedServiceResource:
        """Persist identity, binding and host edge atomically."""

    async def async_reconcile_instance(
        self,
        name: str,
        kind: ResourceKind,
        binding: ProviderBinding,
        host_id: UUID | None,
    ) -> RegistryResource:
        """Accept an external identity once, optionally linking existing inventory."""

    async def async_link_service(
        self, service_id: UUID, host_id: UUID | None
    ) -> RegistryResource:
        """Change a service's optional host association atomically."""

    async def async_relations(
        self, resource_id: UUID, limit: int, offset: int
    ) -> tuple[ResourceRelationship, ...]:
        """Read the incident relationships of an active resource."""

    async def async_add_relation(self, relation: ResourceRelationship) -> None:
        """Validate existence, uniqueness and cycles before writing."""

    async def async_remove_relation(self, relation: ResourceRelationship) -> bool:
        """Remove an explicit edge, preserving service/host consistency."""

    async def async_remove(self, resource_id: UUID) -> bool:
        """Tombstone non-host inventory without performing remote operations."""


class ResourceRegistry:
    def __init__(self, store: ResourceStore, policy: PolicyGuard | None = None) -> None:
        self._store = store
        self._policy = policy or PolicyGuard()

    async def async_list(
        self, limit: int = 25, offset: int = 0
    ) -> tuple[RegistryResource, ...]:
        _page(limit, offset)
        return await self._store.async_list(limit, offset)

    async def async_get(self, resource_id: UUID) -> RegistryResource | None:
        return await self._store.async_get(resource_id)

    async def async_create_service(
        self,
        name: str,
        service_type: str,
        binding: ProviderBinding,
        host_id: UUID | None = None,
    ) -> ManagedServiceResource:
        await self._policy.async_require(Permission.RESOURCE_WRITE)
        resource = ManagedServiceResource(
            uuid4(),
            _name(name),
            service_type,
            binding,
            ResourceRef(ResourceKind.HOST, host_id) if host_id else None,
        )
        return await self._store.async_add_service(resource)

    async def async_reconcile_instance(
        self,
        name: str,
        kind: ResourceKind,
        binding: ProviderBinding,
        host_id: UUID | None = None,
    ) -> RegistryResource:
        await self._policy.async_require(Permission.RESOURCE_WRITE)
        return await self._store.async_reconcile_instance(
            _name(name), kind, binding, host_id
        )

    async def async_link_service(
        self, service_id: UUID, host_id: UUID | None
    ) -> RegistryResource:
        await self._policy.async_require(Permission.RESOURCE_WRITE)
        return await self._store.async_link_service(service_id, host_id)

    async def async_relations(
        self, resource_id: UUID, limit: int = 100, offset: int = 0
    ) -> tuple[ResourceRelationship, ...]:
        _page(limit, offset)
        return await self._store.async_relations(resource_id, limit, offset)

    async def async_add_relation(self, relation: ResourceRelationship) -> None:
        await self._policy.async_require(Permission.RESOURCE_WRITE)
        await self._store.async_add_relation(relation)

    async def async_remove_relation(self, relation: ResourceRelationship) -> bool:
        await self._policy.async_require(Permission.RESOURCE_WRITE)
        return await self._store.async_remove_relation(relation)

    async def async_remove(self, resource_id: UUID) -> bool:
        await self._policy.async_require(Permission.RESOURCE_WRITE)
        return await self._store.async_remove(resource_id)


def _name(name: str) -> str:
    name = name.strip()
    if not name or len(name) > 100:
        raise RegistryConflict("Invalid resource name")
    return name


def _page(limit: int, offset: int) -> None:
    if not 1 <= limit <= 100 or offset < 0:
        raise RegistryConflict("Invalid resource page")
