"""Group use cases depend only on a typed persistence port."""

from typing import Protocol
from uuid import UUID

from .entities import (
    MAX_RESOURCES,
    Group,
    GroupConflict,
    ResourceFacts,
    SmartRule,
    matches,
)


class GroupStore(Protocol):
    async def async_list(
        self, query: str, limit: int, offset: int
    ) -> tuple[Group, ...]: ...
    async def async_get(self, group_id: UUID) -> Group | None: ...
    async def async_save(self, group: Group, *, create: bool) -> None: ...
    async def async_delete(self, group_id: UUID) -> bool: ...
    async def async_tags(self, resource_id: UUID, tags: frozenset[str]) -> None: ...
    async def async_snapshot(self) -> tuple[ResourceFacts, ...]: ...


class GroupService:
    def __init__(self, store: GroupStore) -> None:
        self._store = store

    async def async_list(
        self, query: str, limit: int, offset: int
    ) -> tuple[Group, ...]:
        return await self._store.async_list(query, limit, offset)

    async def async_get(self, group_id: UUID) -> Group | None:
        return await self._store.async_get(group_id)

    async def async_save(self, group: Group, *, create: bool) -> None:
        await self._store.async_save(group, create=create)

    async def async_delete(self, group_id: UUID) -> bool:
        return await self._store.async_delete(group_id)

    async def async_tags(self, resource_id: UUID, tags: frozenset[str]) -> None:
        from .entities import validate_tag

        if len(tags) > 32:
            raise GroupConflict("Too many resource tags")
        for tag in tags:
            validate_tag(tag)
        await self._store.async_tags(resource_id, tags)

    async def async_preview(
        self, rule: SmartRule | None, members: tuple[UUID, ...] | None = None
    ) -> tuple[ResourceFacts, ...]:
        snapshot = await self._store.async_snapshot()
        if len(snapshot) > MAX_RESOURCES:
            raise GroupConflict("Inventory exceeds the bounded preview limit")
        selected = frozenset(members) if members is not None else None
        return tuple(
            resource
            for resource in snapshot
            if (selected is None or resource.id in selected)
            and (rule is None or matches(rule, resource))
        )
