"""Versioned Linux bindings; assessment is descriptive, never authorization."""

from dataclasses import dataclass
from enum import StrEnum

from ..contracts.capabilities import (
    AuthorizationRequirement,
    CapabilityAssessment,
    CapabilityDefinition,
    CapabilityKey,
    CapabilityState,
    ExecutionMode,
    RecoveryMode,
    RiskClass,
    SchemaRef,
)
from ..contracts.resources import ResourceKind, ResourceRef
from .domain import PackageSelection, PackageStatus
from .ports import PackageProvider


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
    provider: PackageProvider

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

    provider: PackageProvider
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
