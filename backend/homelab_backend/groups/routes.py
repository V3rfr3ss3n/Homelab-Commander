"""Authenticated metadata routes; previews do not schedule or authorize actions."""

from collections.abc import Awaitable, Sequence
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, FastAPI, HTTPException, Query, Response
from fastapi.params import Depends
from pydantic import BaseModel, ConfigDict

from ..contracts.resources import ResourceKind
from .application import GroupService
from .entities import GroupConflict, ResourceFacts
from .schemas import GroupData, GroupInput, TagData


class ResourcePage(BaseModel):
    model_config = ConfigDict(frozen=True)
    total: int
    items: tuple[ResourceFacts, ...]
    limit: int
    offset: int


async def _operation[T](operation: Awaitable[T]) -> T:
    try:
        return await operation
    except GroupConflict as error:
        raise HTTPException(409, str(error)) from None


def install_group_routes(
    app: FastAPI,
    service: GroupService,
    external: Sequence[Depends],
    ui_read: Sequence[Depends],
    ui_write: Sequence[Depends],
) -> None:
    for prefix, read, write in [
        ("/api/v1", external, external),
        ("/ui-api", ui_read, ui_write),
    ]:
        router = APIRouter(prefix=prefix)

        @router.get("/groups", dependencies=read)
        async def list_groups(
            query: str = Query(default="", max_length=100),
            limit: int = Query(default=25, ge=1, le=100),
            offset: int = Query(default=0, ge=0),
        ) -> tuple[GroupData, ...]:
            return tuple(
                GroupData.from_domain(g)
                for g in await _operation(service.async_list(query, limit, offset))
            )

        @router.post("/groups/preview", dependencies=write)
        async def preview(
            data: GroupInput,
            limit: int = Query(default=25, ge=1, le=100),
            offset: int = Query(default=0, ge=0),
        ) -> ResourcePage:
            group = data.domain(uuid4())
            resources = await _operation(
                service.async_preview(group.rule, None if group.rule else group.members)
            )
            return ResourcePage(
                total=len(resources),
                items=resources[offset : offset + limit],
                limit=limit,
                offset=offset,
            )

        @router.get("/group-resources", dependencies=read)
        async def resources(
            query: str = Query(default="", max_length=100),
            kind: ResourceKind | None = None,
            tag: str | None = Query(default=None, max_length=48),
            group_id: UUID | None = None,
            sort: Literal["name", "kind"] = "name",
            direction: Literal["asc", "desc"] = "asc",
            limit: int = Query(default=25, ge=1, le=100),
            offset: int = Query(default=0, ge=0),
        ) -> ResourcePage:
            group = await _operation(service.async_get(group_id)) if group_id else None
            if group_id and group is None:
                raise HTTPException(404, "Group not found")
            snapshot = await _operation(
                service.async_preview(
                    group.rule if group else None,
                    group.members if group and group.rule is None else None,
                )
            )
            selected = tuple(
                r
                for r in snapshot
                if query.casefold() in r.name.casefold()
                and (kind is None or kind == r.kind)
                and (tag is None or tag in r.tags)
            )
            selected = tuple(
                sorted(
                    selected,
                    key=lambda resource: (
                        resource.kind.value
                        if sort == "kind"
                        else resource.name.casefold(),
                        resource.name.casefold(),
                        str(resource.id),
                    ),
                    reverse=direction == "desc",
                )
            )
            return ResourcePage(
                total=len(selected),
                items=selected[offset : offset + limit],
                limit=limit,
                offset=offset,
            )

        @router.put(
            "/resources/{resource_id}/tags", dependencies=write, status_code=204
        )
        async def tags(resource_id: UUID, data: TagData) -> Response:
            await _operation(service.async_tags(resource_id, data.tags))
            return Response(status_code=204)

        @router.post("/groups", dependencies=write, status_code=201)
        async def create(data: GroupInput) -> GroupData:
            group = data.domain(uuid4())
            await _operation(service.async_save(group, create=True))
            return GroupData.from_domain(group)

        @router.get("/groups/{group_id}", dependencies=read)
        async def get(group_id: UUID) -> GroupData:
            group = await _operation(service.async_get(group_id))
            if group is None:
                raise HTTPException(404, "Group not found")
            return GroupData.from_domain(group)

        @router.put("/groups/{group_id}", dependencies=write)
        async def update(group_id: UUID, data: GroupInput) -> GroupData:
            group = data.domain(group_id)
            await _operation(service.async_save(group, create=False))
            return GroupData.from_domain(group)

        @router.get("/groups/{group_id}/resources", dependencies=read)
        async def members(
            group_id: UUID,
            limit: int = Query(default=25, ge=1, le=100),
            offset: int = Query(default=0, ge=0),
        ) -> ResourcePage:
            group = await _operation(service.async_get(group_id))
            if group is None:
                raise HTTPException(404, "Group not found")
            selected = await _operation(
                service.async_preview(group.rule, None if group.rule else group.members)
            )
            return ResourcePage(
                total=len(selected),
                items=selected[offset : offset + limit],
                limit=limit,
                offset=offset,
            )

        @router.delete("/groups/{group_id}", dependencies=write, status_code=204)
        async def delete(group_id: UUID) -> Response:
            if not await service.async_delete(group_id):
                raise HTTPException(404, "Group not found")
            return Response(status_code=204)

        app.include_router(router)
