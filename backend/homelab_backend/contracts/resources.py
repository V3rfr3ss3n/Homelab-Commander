"""Provider-neutral identities and directed resource relationships."""

import re
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID


class ResourceKind(StrEnum):
    HOST = "host"
    MANAGED_SERVICE = "managed_service"
    VIRTUAL_MACHINE = "virtual_machine"
    CONTAINER = "container"


@dataclass(frozen=True, slots=True)
class ResourceRef:
    """Internal identity; external provider identifiers never replace this UUID."""

    kind: ResourceKind
    id: UUID


@dataclass(frozen=True, slots=True)
class ProviderBinding:
    """Reference provider configuration, never embed credentials or endpoints."""

    provider_id: str
    connection_id: UUID
    external_id: str = field(repr=False)

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", self.provider_id):
            raise ValueError("Invalid provider contract identifier")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", self.external_id):
            raise ValueError("Invalid opaque provider resource identifier")


@dataclass(frozen=True, slots=True)
class HostResource:
    """The existing host UUID is the resource UUID, without a new identity."""

    id: UUID
    name: str

    @property
    def ref(self) -> ResourceRef:
        return ResourceRef(ResourceKind.HOST, self.id)


@dataclass(frozen=True, slots=True)
class ManagedServiceResource:
    """An API-managed service can exist without any host or SSH association."""

    id: UUID
    name: str
    service_type: str
    binding: ProviderBinding
    host: ResourceRef | None = None

    def __post_init__(self) -> None:
        if self.binding.connection_id == self.id:
            raise ValueError("Service and provider connection identities must differ")
        if not re.fullmatch(
            r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*", self.service_type
        ):
            raise ValueError("Invalid service type")
        if self.host is not None and (
            self.host.kind is not ResourceKind.HOST or self.host.id == self.id
        ):
            raise ValueError("Service host must reference a distinct existing host")

    @property
    def ref(self) -> ResourceRef:
        return ResourceRef(ResourceKind.MANAGED_SERVICE, self.id)


class RelationshipKind(StrEnum):
    RUNS_SERVICE = "runs_service"
    HOSTS_INSTANCE = "hosts_instance"
    CORRESPONDS_TO_HOST = "corresponds_to_host"
    MANAGED_BY = "managed_by"


@dataclass(frozen=True, slots=True)
class ResourceRelationship:
    """Validate edge direction locally; registry validates existence and cycles."""

    kind: RelationshipKind
    source: ResourceRef
    target: ResourceRef

    def __post_init__(self) -> None:
        source, target = self.source.kind, self.target.kind
        instance = {ResourceKind.VIRTUAL_MACHINE, ResourceKind.CONTAINER}
        valid = {
            RelationshipKind.RUNS_SERVICE: source is ResourceKind.HOST
            and target is ResourceKind.MANAGED_SERVICE,
            RelationshipKind.HOSTS_INSTANCE: source is ResourceKind.HOST
            and target in instance,
            RelationshipKind.CORRESPONDS_TO_HOST: source in instance
            and target is ResourceKind.HOST,
            RelationshipKind.MANAGED_BY: source
            in instance | {ResourceKind.MANAGED_SERVICE}
            and target is ResourceKind.MANAGED_SERVICE,
        }[self.kind]
        if not valid or self.source.id == self.target.id:
            raise ValueError("Invalid resource relationship endpoints")
