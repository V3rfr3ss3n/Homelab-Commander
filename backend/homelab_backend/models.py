"""Typed API and persistence boundary models."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

HostName = Annotated[str, Field(min_length=1, max_length=100)]
HostAddress = Annotated[
    str, Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9][A-Za-z0-9.:-]*$")
]
SshUser = Annotated[str, Field(pattern=r"^[a-z_][a-z0-9_-]{0,31}$")]


class HostCreate(BaseModel):
    """Input accepted when registering a managed host."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: HostName
    address: HostAddress
    port: int = Field(default=22, ge=1, le=65535)
    username: SshUser
    package_provider: str = Field(default="debian_apt", pattern=r"^[a-z][a-z0-9_]+$")


class HostPatch(BaseModel):
    """Fields that may be changed without changing host identity."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: HostName | None = None
    address: HostAddress | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    username: SshUser | None = None
    package_provider: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]+$")


class Host(BaseModel):
    """Persisted host with stable UUID identity."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    address: str
    port: int
    username: str
    package_provider: str
    distribution: str | None = None
    distribution_version: str | None = None
    kernel: str | None = None
    updates: int = 0
    security_updates: int = 0
    reboot_required: bool = False
    status: str | None = None
    checked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class JobAction(StrEnum):
    """Built-in operations understood by the native executor."""

    TEST_CONNECTION = "test_connection"
    CHECK_UPDATES = "check_updates"
    UPDATE = "update"
    REBOOT = "reboot"
    CUSTOM_TASK = "custom_task"


class JobState(StrEnum):
    """Persistent queue lifecycle."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class Job(BaseModel):
    """Persistent asynchronous job returned by the API."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    action: JobAction
    host_id: UUID | None
    custom_task_id: UUID | None = None
    state: JobState
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_code: str | None = None
    reboot_required: bool | None = None


class JobLog(BaseModel):
    """Bounded redacted output for one job."""

    job_id: UUID
    output: str
    truncated: bool


class CustomTaskMode(StrEnum):
    """Explicit execution semantics for a user-defined task."""

    COMMAND = "command"
    SHELL = "shell"


class CustomTaskCreate(BaseModel):
    """Validated custom task definition accepted by the API."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    mode: CustomTaskMode = CustomTaskMode.COMMAND
    argv: tuple[str, ...] | None = None
    shell_command: str | None = Field(default=None, max_length=4096)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_execution(self) -> CustomTaskCreate:
        """Require exactly one execution representation without NUL bytes."""
        if self.mode is CustomTaskMode.COMMAND:
            if not self.argv or self.shell_command is not None:
                raise ValueError("Command tasks require argv and no shell command")
            if len(self.argv) > 64 or any(
                not value or len(value) > 1024 or "\x00" in value for value in self.argv
            ):
                raise ValueError("Command arguments are invalid")
        elif (
            self.argv is not None
            or not self.shell_command
            or "\x00" in self.shell_command
        ):
            raise ValueError("Shell tasks require one non-empty shell command")
        return self


class CustomTaskPatch(BaseModel):
    """Partial custom task update."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    mode: CustomTaskMode | None = None
    argv: tuple[str, ...] | None = None
    shell_command: str | None = Field(default=None, max_length=4096)
    enabled: bool | None = None


class CustomTask(BaseModel):
    """Persistent custom operation exposed to trusted clients."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    description: str
    mode: CustomTaskMode
    argv: tuple[str, ...] | None
    shell_command: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class PublicKeyResponse(BaseModel):
    """Public part of the backend-managed SSH identity."""

    algorithm: str
    public_key: str


class InfoResponse(BaseModel):
    """Non-secret backend build and capability information."""

    name: str
    version: str
    api_version: str
    capabilities: tuple[str, ...]
