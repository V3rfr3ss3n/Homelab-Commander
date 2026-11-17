"""Authorization service and request-local identity; no HTTP or SQLite imports."""

import logging
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from ..contracts.resources import ResourceRef
from .domain import SYSTEM, Permission, PolicyEngine, Principal

_ACTOR: ContextVar[Principal] = ContextVar("homelab_principal", default=SYSTEM)
_LOGGER = logging.getLogger(__name__)


def current_principal() -> Principal:
    return _ACTOR.get()


def bind_principal(principal: Principal) -> Token[Principal]:
    return _ACTOR.set(principal)


def reset_principal(token: Token[Principal]) -> None:
    _ACTOR.reset(token)


@contextmanager
def principal_scope(principal: Principal) -> Generator[None]:
    token = _ACTOR.set(principal)
    try:
        yield
    finally:
        _ACTOR.reset(token)


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: UUID
    at: datetime
    principal: Principal
    permission: Permission
    target: ResourceRef | None
    code: str


class AuditPort(Protocol):
    async def async_append(self, event: AuditEvent) -> None:
        """Append safe bounded metadata; no request/command/provider text."""


class AuthorizationDenied(Exception):
    """Safe policy denial; never a raw rule, request or provider error."""

    def __init__(self, code: str = "policy_denied") -> None:
        super().__init__("This action is not permitted by backend policy")
        self.code = code


class PolicyGuard:
    def __init__(
        self, audit: AuditPort | None = None, *, engine: PolicyEngine | None = None
    ) -> None:
        self.engine = engine or PolicyEngine()
        self._audit = audit

    async def async_require(
        self,
        permission: Permission,
        target: ResourceRef | None = None,
        *,
        principal: Principal | None = None,
        operation: str | None = None,
    ) -> None:
        actor = principal or current_principal()
        decision = self.engine.decide(actor, permission, target, operation)
        if not decision.allowed:
            await self.async_deny(permission, target, actor, decision.code)

    async def async_deny(
        self,
        permission: Permission,
        target: ResourceRef | None,
        principal: Principal,
        code: str,
    ) -> None:
        event = AuditEvent(
            uuid4(), datetime.now(UTC), principal, permission, target, code
        )
        if self._audit:
            await self._audit.async_append(event)
        else:
            _LOGGER.warning(
                "Authorization denied code=%s permission=%s reference=%s",
                code,
                permission,
                event.id,
            )
        raise AuthorizationDenied(code)
