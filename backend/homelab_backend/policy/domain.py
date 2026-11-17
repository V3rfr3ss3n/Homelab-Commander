"""Pure identity/risk policy: unknown subjects, operations and grants deny."""

import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import NAMESPACE_OID, UUID, uuid5

from ..contracts.capabilities import RiskClass
from ..contracts.resources import ResourceKind, ResourceRef


class PrincipalKind(StrEnum):
    ADMIN = "admin"
    HUMAN = "human"
    SYSTEM = "system"
    STATUS = "status"
    AGENT = "agent"
    AUTOMATION = "automation"
    ANONYMOUS = "anonymous"


class AuthSource(StrEnum):
    INTERNAL = "internal"
    API = "api"
    UI = "ui"
    INGRESS = "ingress"
    LEGACY = "legacy"
    AGENT = "agent"
    AUTOMATION = "automation"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class Principal:
    """Server-owned subject; never a token, session ID or claimed person name."""

    id: UUID | None
    kind: PrincipalKind
    source: AuthSource

    def __post_init__(self) -> None:
        sources = {
            PrincipalKind.ADMIN: {AuthSource.API, AuthSource.LEGACY},
            PrincipalKind.HUMAN: {AuthSource.UI, AuthSource.INGRESS},
            PrincipalKind.SYSTEM: {AuthSource.INTERNAL},
            PrincipalKind.STATUS: {AuthSource.INTERNAL},
            PrincipalKind.AGENT: {AuthSource.AGENT},
            PrincipalKind.AUTOMATION: {AuthSource.AUTOMATION},
            PrincipalKind.ANONYMOUS: {AuthSource.NONE},
        }
        if self.source not in sources[self.kind] or (self.id is None) != (
            self.kind is PrincipalKind.ANONYMOUS
        ):
            raise ValueError("Invalid principal authority source")


SYSTEM = Principal(
    uuid5(NAMESPACE_OID, "homelab_commander.internal"),
    PrincipalKind.SYSTEM,
    AuthSource.INTERNAL,
)
ANONYMOUS = Principal(None, PrincipalKind.ANONYMOUS, AuthSource.NONE)


def entrance(kind: PrincipalKind, source: AuthSource) -> Principal:
    """Shared legacy entrances are identified honestly, not as individual users."""
    return Principal(uuid5(NAMESPACE_OID, f"homelab_commander.{source}"), kind, source)


class Permission(StrEnum):
    LEGACY_API = "legacy.api"
    HOST_WRITE = "host.write"
    HOST_STATUS = "host.status"
    TASK_WRITE = "task.write"
    TASK_ASSIGN = "task.assign"
    TASK_PROBE = "task.probe"
    GROUP_WRITE = "group.write"
    TAG_WRITE = "tag.write"
    RESOURCE_WRITE = "resource.write"
    PREFERENCE_WRITE = "preference.write"
    REVIEW_JOB = "job.review"
    SSH_IDENTITY = "ssh.identity"
    HOST_SETUP = "host.setup"
    EXECUTE = "operation.execute"
    APPROVAL_REQUEST = "approval.request"
    APPROVAL_DECIDE = "approval.decide"


@dataclass(frozen=True, slots=True)
class OperationPolicy:
    operation: str
    kinds: frozenset[ResourceKind]
    risk: RiskClass
    # Compatibility applies only to the five existing explicit Host actions.
    legacy_admin: bool = False

    def __post_init__(self) -> None:
        if (
            not re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", self.operation)
            or not self.kinds
        ):
            raise ValueError("Invalid operation policy")
        if self.legacy_admin and self.operation not in LEGACY_OPERATIONS:
            raise ValueError("Legacy authority cannot be extended to new operations")

    @property
    def approval_required(self) -> bool:
        return not self.legacy_admin and self.risk in {
            RiskClass.DISRUPTIVE,
            RiskClass.DESTRUCTIVE,
        }


LEGACY_OPERATIONS = {
    "linux.test_connection": RiskClass.READ_ONLY,
    "linux.check_updates": RiskClass.READ_ONLY,
    "linux.update": RiskClass.MUTATING,
    "linux.reboot": RiskClass.DISRUPTIVE,
    "linux.custom_task": RiskClass.DESTRUCTIVE,
}


@dataclass(frozen=True, slots=True)
class Decision:
    allowed: bool
    code: str


class PolicyEngine:
    """Static M1 policies; agent/automation execution is never enabled here."""

    def __init__(self, operations: tuple[OperationPolicy, ...] = ()) -> None:
        defaults = tuple(
            OperationPolicy(name, frozenset({ResourceKind.HOST}), risk, True)
            for name, risk in LEGACY_OPERATIONS.items()
        )
        self._operations = {item.operation: item for item in (*defaults, *operations)}
        if len(self._operations) != len(defaults) + len(operations):
            raise ValueError("Duplicate operation policy")

    def operation(self, operation: str, target: ResourceRef) -> OperationPolicy | None:
        definition = self._operations.get(operation)
        return definition if definition and target.kind in definition.kinds else None

    def decide(
        self,
        principal: Principal,
        permission: Permission | str,
        target: ResourceRef | None = None,
        operation: str | None = None,
    ) -> Decision:
        if not isinstance(permission, Permission):
            return Decision(False, "policy_denied")
        if principal.id is None or principal.kind is PrincipalKind.ANONYMOUS:
            return Decision(False, "identity_required")
        if permission is Permission.LEGACY_API:
            allowed = (
                principal.kind is PrincipalKind.ADMIN
                and principal.source is AuthSource.API
            )
            return Decision(allowed, "permitted" if allowed else "policy_denied")
        if permission is Permission.APPROVAL_REQUEST and principal.kind in {
            PrincipalKind.AGENT,
            PrincipalKind.ADMIN,
            PrincipalKind.HUMAN,
            PrincipalKind.SYSTEM,
        }:
            if (
                target is not None
                and operation is not None
                and self.operation(operation, target)
            ):
                return Decision(True, "permitted")
            return Decision(False, "operation_unsupported")
        if permission is Permission.APPROVAL_DECIDE:
            human = principal.kind is PrincipalKind.HUMAN and principal.source in {
                AuthSource.UI,
                AuthSource.INGRESS,
            }
            return Decision(human, "permitted" if human else "human_approval_required")
        if principal.kind in {PrincipalKind.AGENT, PrincipalKind.AUTOMATION}:
            return Decision(False, "policy_denied")
        if permission is Permission.EXECUTE:
            definition = (
                self.operation(operation, target)
                if operation is not None and target is not None
                else None
            )
            if definition is None:
                return Decision(False, "operation_unsupported")
            if principal.kind is PrincipalKind.STATUS and operation in {
                "linux.check_updates",
                "linux.test_connection",
            }:
                return Decision(True, "permitted")
            if principal.kind not in {
                PrincipalKind.ADMIN,
                PrincipalKind.HUMAN,
                PrincipalKind.SYSTEM,
            }:
                return Decision(False, "policy_denied")
            return Decision(True, "permitted")
        if principal.kind is PrincipalKind.STATUS:
            return Decision(
                permission is Permission.HOST_STATUS,
                "permitted"
                if permission is Permission.HOST_STATUS
                else "policy_denied",
            )
        return Decision(True, "permitted")
