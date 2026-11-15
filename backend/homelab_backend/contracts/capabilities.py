"""Versioned capability declarations; discovery never grants execution rights."""

import re
from dataclasses import dataclass
from enum import StrEnum

from .resources import ResourceKind, ResourceRef


def _identifier(value: str) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", value):
        raise ValueError("Invalid namespaced contract identifier")


@dataclass(frozen=True, slots=True)
class ContractVersion:
    major: int = 1
    minor: int = 0

    def __post_init__(self) -> None:
        if self.major < 1 or self.minor < 0:
            raise ValueError("Invalid contract version")


@dataclass(frozen=True, slots=True)
class SchemaRef:
    """A named validated payload schema, not a URL or arbitrary executable schema."""

    id: str
    version: ContractVersion = ContractVersion()

    def __post_init__(self) -> None:
        _identifier(self.id)


@dataclass(frozen=True, slots=True)
class CapabilityKey:
    id: str
    version: ContractVersion = ContractVersion()

    def __post_init__(self) -> None:
        _identifier(self.id)


class CapabilityState(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"
    POLICY_BLOCKED = "policy_blocked"


class RiskClass(StrEnum):
    READ_ONLY = "read_only"
    MUTATING = "mutating"
    DISRUPTIVE = "disruptive"
    DESTRUCTIVE = "destructive"


class ExecutionMode(StrEnum):
    READ = "read"
    JOB = "job"


class RecoveryMode(StrEnum):
    RETRY_READ = "retry_read"
    REVALIDATE = "revalidate"
    NEVER_REPLAY = "never_replay"


@dataclass(frozen=True, slots=True)
class AuthorizationRequirement:
    permission: str
    human_approval: bool = False

    def __post_init__(self) -> None:
        _identifier(self.permission)


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    key: CapabilityKey
    resource_kinds: frozenset[ResourceKind]
    input_schema: SchemaRef
    output_schema: SchemaRef
    authorization: AuthorizationRequirement
    risk: RiskClass
    execution: ExecutionMode
    recovery: RecoveryMode
    prerequisites: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.resource_kinds:
            raise ValueError("Capability requires a supported resource kind")
        if self.risk is not RiskClass.READ_ONLY and (
            self.execution is ExecutionMode.READ
            or self.recovery is RecoveryMode.RETRY_READ
        ):
            raise ValueError("Mutations require jobs and guarded recovery")
        if self.risk in {RiskClass.DISRUPTIVE, RiskClass.DESTRUCTIVE} and (
            not self.authorization.human_approval
            or self.recovery is not RecoveryMode.NEVER_REPLAY
        ):
            raise ValueError("Disruptive actions require human approval and no replay")
        for prerequisite in self.prerequisites:
            _identifier(prerequisite)


@dataclass(frozen=True, slots=True)
class CapabilityAssessment:
    """Availability is evidence about one resource, never an authorization token."""

    target: ResourceRef
    key: CapabilityKey
    state: CapabilityState
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.state is not CapabilityState.SUPPORTED and not self.reason_codes:
            raise ValueError("Unavailable capabilities require a safe reason code")
        for code in self.reason_codes:
            _identifier(code)
