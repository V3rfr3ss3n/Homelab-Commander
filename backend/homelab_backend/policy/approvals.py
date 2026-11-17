"""Immutable, expiring approval requests and a nondelegable human decision service."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..contracts.capabilities import RiskClass
from ..contracts.resources import ResourceRef
from .application import PolicyGuard, current_principal
from .domain import Permission, Principal


class ApprovalState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CONSUMED = "consumed"


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: UUID
    requested_by: Principal
    target: ResourceRef
    operation: str = Field(
        pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$", max_length=100
    )
    risk: RiskClass
    scope_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    observed_state: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_window(self) -> ApprovalRequest:
        if (
            self.created_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not (
                timedelta(0)
                < self.expires_at - self.created_at
                <= timedelta(minutes=15)
            )
        ):
            raise ValueError("Invalid approval time window")
        return self


class ApprovalRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request: ApprovalRequest
    state: ApprovalState = ApprovalState.PENDING
    decided_by: UUID | None = None
    consumed_by_job: UUID | None = None


class ApprovalStore(Protocol):
    async def async_create(self, request: ApprovalRequest) -> ApprovalRecord: ...
    async def async_get(self, request_id: UUID) -> ApprovalRecord | None: ...
    async def async_decide(
        self, request_id: UUID, principal: Principal, approve: bool, now: datetime
    ) -> bool: ...
    async def async_consume(
        self, request: ApprovalRequest, job_id: UUID, now: datetime
    ) -> bool: ...


class StateValidator(Protocol):
    async def async_is_current(self, request: ApprovalRequest) -> bool:
        """Validate observed resource/prerequisite state from a trusted adapter."""


def utc_now() -> datetime:
    return datetime.now(UTC)


class ApprovalService:
    def __init__(
        self,
        store: ApprovalStore,
        guard: PolicyGuard,
        validator: StateValidator,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._store = store
        self._guard = guard
        self._validator = validator
        self._clock = clock

    async def async_request(
        self,
        target: ResourceRef,
        operation: str,
        scope_digest: str,
        observed_state: str,
        *,
        lifetime: timedelta = timedelta(minutes=15),
    ) -> ApprovalRecord:
        await self._guard.async_require(
            Permission.APPROVAL_REQUEST, target, operation=operation
        )
        definition = self._guard.engine.operation(operation, target)
        assert definition is not None
        now = self._clock()
        if now.tzinfo is None or not timedelta(0) < lifetime <= timedelta(minutes=15):
            raise ValueError("Approval lifetime must be within fifteen minutes")
        request = ApprovalRequest(
            id=uuid4(),
            requested_by=current_principal(),
            target=target,
            operation=operation,
            risk=definition.risk,
            scope_digest=scope_digest,
            observed_state=observed_state,
            created_at=now,
            expires_at=now + lifetime,
        )
        return await self._store.async_create(request)

    async def async_decide(self, request_id: UUID, *, approve: bool) -> None:
        await self._guard.async_require(Permission.APPROVAL_DECIDE)
        if not await self._store.async_decide(
            request_id, current_principal(), approve, self._clock()
        ):
            await self._deny(None, "approval_unavailable")

    async def async_validate(
        self, request_id: UUID, target: ResourceRef, operation: str, scope_digest: str
    ) -> ApprovalRequest:
        actor = current_principal()
        await self._guard.async_require(Permission.EXECUTE, target, operation=operation)
        record = await self._store.async_get(request_id)
        definition = self._guard.engine.operation(operation, target)
        if (
            record is None
            or definition is None
            or record.request.risk != definition.risk
            or record.state is not ApprovalState.APPROVED
            or record.request.expires_at <= self._clock()
            or record.request.requested_by != actor
            or record.request.target != target
            or record.request.operation != operation
            or record.request.scope_digest != scope_digest
        ):
            await self._deny(target, "approval_unavailable")
        assert record is not None
        if not await self._validator.async_is_current(record.request):
            await self._deny(target, "approval_state_changed")
        return record.request

    async def async_consume(
        self,
        request_id: UUID,
        target: ResourceRef,
        operation: str,
        scope_digest: str,
        job_id: UUID,
    ) -> None:
        request = await self.async_validate(request_id, target, operation, scope_digest)
        if not await self._store.async_consume(request, job_id, self._clock()):
            await self._deny(target, "approval_unavailable")

    async def _deny(self, target: ResourceRef | None, code: str) -> None:
        await self._guard.async_deny(
            Permission.EXECUTE, target, current_principal(), code
        )
