"""Immutable, credential-free execution snapshots; never authorization grants."""

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..contracts.capabilities import RecoveryMode
from ..contracts.resources import ResourceRef


class JobCaller(StrEnum):
    """Authenticated entrance, not a claimed human identity or session identifier."""

    EXTERNAL_ADMIN = "external_admin"
    UI_ADMIN = "ui_admin"
    INGRESS_ADMIN = "ingress_admin"
    VISIBLE_STATUS = "visible_status"
    INTERNAL_ADMIN = "internal_admin"
    LEGACY_ADMIN = "legacy_admin"


class ExecutionContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    caller: JobCaller = JobCaller.INTERNAL_ADMIN
    # Reserved for #46. No caller may turn this reference into permission.
    approval_id: UUID | None = None


class OperationScope(BaseModel):
    """Exact target, validated legacy parameters and server-resolved conflict set.

    Future feature-specific parameters need a typed extension, never arbitrary
    provider JSON, command strings or credentials in this public value.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    target: ResourceRef
    operation: str = Field(
        pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$", max_length=100
    )
    execution_host_id: UUID | None = None
    conflicts: tuple[ResourceRef, ...] = Field(min_length=1, max_length=2)
    recovery: RecoveryMode = RecoveryMode.NEVER_REPLAY
    package_name: str | None = Field(
        default=None, max_length=255, pattern=r"^[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?$"
    )
    package_names: tuple[
        Annotated[
            str, Field(max_length=255, pattern=r"^[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?$")
        ],
        ...,
    ] = Field(default=(), max_length=50)
    custom_task_id: UUID | None = None
    task_revision: str | None = Field(default=None, max_length=64)
    connection_revision: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_conflicts(self) -> OperationScope:
        canonical = tuple(
            sorted(set(self.conflicts), key=lambda ref: (ref.kind, ref.id))
        )
        if self.conflicts != canonical or self.target not in canonical:
            raise ValueError("Conflict set must be canonical and contain the target")
        if self.package_name is not None and self.package_names:
            raise ValueError("Package scopes are mutually exclusive")
        if self.package_names != tuple(sorted(set(self.package_names))):
            raise ValueError("Package selection must be canonical")
        return self


class JobExecution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    scope: OperationScope
    context: ExecutionContext = ExecutionContext()
