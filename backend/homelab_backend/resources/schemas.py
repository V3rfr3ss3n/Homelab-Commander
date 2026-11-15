"""Validated HTTP DTOs; provider secrets never enter resource metadata."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..contracts.resources import (
    HostResource,
    ManagedServiceResource,
    ProviderBinding,
    RelationshipKind,
    ResourceKind,
    ResourceRef,
    ResourceRelationship,
)
from .entities import RegistryResource

Name = Annotated[str, Field(min_length=1, max_length=100)]


class BindingData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    provider_id: str = Field(pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
    connection_id: UUID
    external_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$", repr=False)

    def to_domain(self) -> ProviderBinding:
        return ProviderBinding(self.provider_id, self.connection_id, self.external_id)


class ServiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: Name
    service_type: str = Field(pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
    binding: BindingData
    host_id: UUID | None = None


class InstanceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: Name
    kind: Literal[ResourceKind.VIRTUAL_MACHINE, ResourceKind.CONTAINER]
    binding: BindingData
    host_id: UUID | None = None


class HostLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    host_id: UUID | None


class RefData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID
    kind: ResourceKind

    def to_domain(self) -> ResourceRef:
        return ResourceRef(self.kind, self.id)


class RelationData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: RelationshipKind
    source: RefData
    target: RefData

    def to_domain(self) -> ResourceRelationship:
        return ResourceRelationship(
            self.kind, self.source.to_domain(), self.target.to_domain()
        )

    @classmethod
    def from_domain(cls, relation: ResourceRelationship) -> RelationData:
        return cls(
            kind=relation.kind,
            source=RefData(kind=relation.source.kind, id=relation.source.id),
            target=RefData(kind=relation.target.kind, id=relation.target.id),
        )


class ResourceData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID
    kind: ResourceKind
    name: str
    service_type: str | None = None
    host_id: UUID | None = None
    binding: BindingData | None = None

    @classmethod
    def from_domain(cls, resource: RegistryResource) -> ResourceData:
        binding = (
            None
            if isinstance(resource, HostResource)
            else BindingData(
                provider_id=resource.binding.provider_id,
                connection_id=resource.binding.connection_id,
                external_id=resource.binding.external_id,
            )
        )
        service = resource if isinstance(resource, ManagedServiceResource) else None
        return cls(
            id=resource.ref.id,
            kind=resource.ref.kind,
            name=resource.name,
            binding=binding,
            service_type=service.service_type if service else None,
            host_id=service.host.id if service and service.host else None,
        )
