"""Versioned Linux bindings; assessment is descriptive, never authorization."""

from dataclasses import dataclass, replace
from enum import StrEnum

from ..contracts.capabilities import (
    AuthorizationRequirement,
    CapabilityAssessment,
    CapabilityDefinition,
    CapabilityKey,
    CapabilityState,
    ContractVersion,
    ExecutionMode,
    RecoveryMode,
    RiskClass,
    SchemaRef,
)
from ..contracts.resources import ResourceKind, ResourceRef
from .domain import PackageSelection, PackageStatus
from .evidence import InventoryEvidence
from .ports import InventoryProvider, ProviderDescriptor


class PackageOperation(StrEnum):
    CHECK = "linux.check_updates"
    UPDATE = "linux.update"


@dataclass(frozen=True, slots=True)
class PackageRequest:
    """Status has no selection; updates carry an explicit immutable scope."""

    operation: PackageOperation
    selection: PackageSelection | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.operation, PackageOperation) or (
            self.selection is not None
            and not isinstance(self.selection, PackageSelection)
        ):
            raise ValueError("Invalid package request scope")
        if (self.operation is PackageOperation.UPDATE) != (self.selection is not None):
            raise ValueError("Invalid package request scope")


@dataclass(frozen=True, slots=True)
class PackageInputValidator:
    operation: PackageOperation
    provider: ProviderDescriptor

    def validate(self, value: object) -> PackageRequest:
        if (
            not isinstance(value, PackageRequest)
            or value.operation is not self.operation
        ):
            raise ValueError("Invalid package request")
        if (
            value.selection is not None
            and value.selection.scope not in self.provider.scopes
        ):
            raise ValueError("Package scope is unsupported")
        return value


class PackageOutputValidator:
    def validate(self, value: object) -> PackageStatus:
        if not isinstance(value, PackageStatus):
            raise ValueError("Invalid normalized package status")
        return value


@dataclass(frozen=True, slots=True)
class PackageCapability:
    """A binding implements CapabilityProvider without adding an execution entrance.

    No readiness probe is performed. A supported kind/operation remains unavailable
    until a future discovery service supplies current host-specific evidence.
    """

    provider: ProviderDescriptor
    operation: PackageOperation

    @property
    def provider_id(self) -> str:
        return self.provider.provider_id

    @property
    def definition(self) -> CapabilityDefinition:
        update = self.operation is PackageOperation.UPDATE
        return CapabilityDefinition(
            key=CapabilityKey(self.operation.value),
            resource_kinds=frozenset({ResourceKind.HOST}),
            input_schema=SchemaRef("linux.package_request"),
            output_schema=SchemaRef("linux.package_status"),
            authorization=AuthorizationRequirement(self.operation.value),
            risk=RiskClass.MUTATING if update else RiskClass.READ_ONLY,
            execution=ExecutionMode.JOB,
            recovery=RecoveryMode.NEVER_REPLAY if update else RecoveryMode.RETRY_READ,
            limitations=("Host readiness must be revalidated before execution",),
        )

    @property
    def input_validator(self) -> PackageInputValidator:
        return PackageInputValidator(self.operation, self.provider)

    @property
    def output_validator(self) -> PackageOutputValidator:
        return PackageOutputValidator()

    async def async_assess(self, target: ResourceRef) -> CapabilityAssessment:
        supported_kind = target.kind is ResourceKind.HOST
        return CapabilityAssessment(
            target,
            self.definition.key,
            CapabilityState.UNAVAILABLE
            if supported_kind
            else CapabilityState.UNSUPPORTED,
            (
                "linux.readiness_unknown"
                if supported_kind
                else "linux.target_unsupported",
            ),
        )


class InventoryOutputValidator:
    def validate(self, value: object) -> InventoryEvidence:
        if not isinstance(value, InventoryEvidence):
            raise ValueError("Invalid qualified package inventory")
        return value


@dataclass(frozen=True, slots=True)
class InventoryCapability:
    """V2 output carries qualified observations; legacy bindings remain v1."""

    provider: InventoryProvider
    operation: PackageOperation

    @property
    def provider_id(self) -> str:
        return self.provider.provider_id

    @property
    def definition(self) -> CapabilityDefinition:
        legacy = PackageCapability(self.provider, self.operation).definition
        return replace(
            legacy,
            key=CapabilityKey(self.operation.value, ContractVersion(2)),
            output_schema=SchemaRef("linux.inventory_evidence"),
        )

    @property
    def input_validator(self) -> PackageInputValidator:
        return PackageInputValidator(self.operation, self.provider)

    @property
    def output_validator(self) -> InventoryOutputValidator:
        return InventoryOutputValidator()

    async def async_assess(self, target: ResourceRef) -> CapabilityAssessment:
        previous = await PackageCapability(self.provider, self.operation).async_assess(
            target
        )
        return replace(previous, key=self.definition.key)


def capability_binding(
    provider: ProviderDescriptor, operation: PackageOperation
) -> PackageCapability | InventoryCapability:
    return (
        InventoryCapability(provider, operation)
        if isinstance(provider, InventoryProvider)
        else PackageCapability(provider, operation)
    )
