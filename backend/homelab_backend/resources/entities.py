"""Immutable registry values built on the accepted core resource contracts."""

from dataclasses import dataclass
from uuid import UUID

from ..contracts.resources import (
    HostResource,
    ManagedServiceResource,
    ProviderBinding,
    ResourceKind,
    ResourceRef,
)


@dataclass(frozen=True, slots=True)
class InfrastructureResource:
    id: UUID
    name: str
    kind: ResourceKind
    binding: ProviderBinding

    def __post_init__(self) -> None:
        if self.kind not in {ResourceKind.VIRTUAL_MACHINE, ResourceKind.CONTAINER}:
            raise ValueError("Invalid infrastructure resource kind")
        if self.id == self.binding.connection_id:
            raise ValueError("Instance and connection identities must differ")

    @property
    def ref(self) -> ResourceRef:
        return ResourceRef(self.kind, self.id)


type RegistryResource = HostResource | ManagedServiceResource | InfrastructureResource


class RegistryConflict(ValueError):
    """Safe operation conflict without infrastructure identifiers or SQL data."""
