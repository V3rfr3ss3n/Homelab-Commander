"""Bounded admin inventory routes isolated from the main composition root."""

from collections.abc import Awaitable, Sequence
from uuid import UUID

from fastapi import APIRouter, FastAPI, HTTPException, Query, Response
from fastapi.params import Depends

from .application import ResourceRegistry
from .entities import RegistryConflict
from .schemas import HostLink, InstanceCreate, RelationData, ResourceData, ServiceCreate


async def _operation[T](operation: Awaitable[T]) -> T:
    try:
        return await operation
    except RegistryConflict as error:
        raise HTTPException(409, str(error)) from None
    except ValueError:
        raise HTTPException(409, "Invalid resource operation") from None


def install_resource_routes(
    app: FastAPI,
    registry: ResourceRegistry,
    external: Sequence[Depends],
    ui_read: Sequence[Depends],
    ui_write: Sequence[Depends],
) -> None:
    """Reuse existing auth/CSRF boundaries; add no remote execution entrance."""
    for prefix, read, write in [
        ("/api/v1", external, external),
        ("/ui-api", ui_read, ui_write),
    ]:
        router = APIRouter(prefix=prefix)

        @router.get("/resources", response_model=list[ResourceData], dependencies=read)
        async def list_resources(
            limit: int = Query(default=25, ge=1, le=100),
            offset: int = Query(default=0, ge=0),
        ) -> tuple[ResourceData, ...]:
            return tuple(
                ResourceData.from_domain(resource)
                for resource in await registry.async_list(limit, offset)
            )

        @router.get(
            "/resources/{resource_id}", response_model=ResourceData, dependencies=read
        )
        async def get_resource(resource_id: UUID) -> ResourceData:
            resource = await registry.async_get(resource_id)
            if resource is None:
                raise HTTPException(404, "Resource not found")
            return ResourceData.from_domain(resource)

        @router.post(
            "/resources/services",
            response_model=ResourceData,
            status_code=201,
            dependencies=write,
        )
        async def create_service(data: ServiceCreate) -> ResourceData:
            resource = await _operation(
                registry.async_create_service(
                    data.name, data.service_type, data.binding.to_domain(), data.host_id
                )
            )
            return ResourceData.from_domain(resource)

        @router.post(
            "/resources/instances", response_model=ResourceData, dependencies=write
        )
        async def reconcile_instance(data: InstanceCreate) -> ResourceData:
            resource = await _operation(
                registry.async_reconcile_instance(
                    data.name, data.kind, data.binding.to_domain(), data.host_id
                )
            )
            return ResourceData.from_domain(resource)

        @router.patch(
            "/resources/{resource_id}/host",
            response_model=ResourceData,
            dependencies=write,
        )
        async def link_host(resource_id: UUID, data: HostLink) -> ResourceData:
            return ResourceData.from_domain(
                await _operation(registry.async_link_service(resource_id, data.host_id))
            )

        @router.get(
            "/resources/{resource_id}/relationships",
            response_model=list[RelationData],
            dependencies=read,
        )
        async def list_relations(
            resource_id: UUID,
            limit: int = Query(default=100, ge=1, le=100),
            offset: int = Query(default=0, ge=0),
        ) -> tuple[RelationData, ...]:
            if await registry.async_get(resource_id) is None:
                raise HTTPException(404, "Resource not found")
            return tuple(
                RelationData.from_domain(item)
                for item in await registry.async_relations(resource_id, limit, offset)
            )

        @router.post(
            "/resource-relationships", response_model=RelationData, dependencies=write
        )
        async def add_relation(data: RelationData) -> RelationData:
            # Contract validation is pure and uses safe static messages.
            try:
                relation = data.to_domain()
            except ValueError:
                raise HTTPException(409, "Invalid resource relationship") from None
            await _operation(registry.async_add_relation(relation))
            return data

        @router.delete("/resource-relationships", status_code=204, dependencies=write)
        async def remove_relation(data: RelationData) -> Response:
            try:
                relation = data.to_domain()
            except ValueError:
                raise HTTPException(409, "Invalid resource relationship") from None
            if not await _operation(registry.async_remove_relation(relation)):
                raise HTTPException(404, "Relationship not found")
            return Response(status_code=204)

        @router.delete("/resources/{resource_id}", status_code=204, dependencies=write)
        async def remove_resource(resource_id: UUID) -> Response:
            if not await _operation(registry.async_remove(resource_id)):
                raise HTTPException(404, "Resource not found")
            return Response(status_code=204)

        app.include_router(router)
