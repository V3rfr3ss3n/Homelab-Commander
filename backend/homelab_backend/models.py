"""Typed API and persistence boundary models."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)

from .execution.scope import JobExecution

HostName = Annotated[str, Field(min_length=1, max_length=100)]
HostAddress = Annotated[
    str, Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9][A-Za-z0-9.:-]*$")
]
SshUser = Annotated[str, Field(pattern=r"^[a-z_][a-z0-9_-]{0,31}$")]
PackageName = Annotated[
    str,
    Field(
        min_length=1,
        max_length=255,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9+_.:-]*$",
    ),
]

MAX_PACKAGE_DETAILS = 50
PackageSourceChoice = Literal["system", "flatpak_system", "flatpak_user"]
PackageSourceId = Literal[
    "apt", "dnf", "zypper", "apk", "pacman", "flatpak_system", "flatpak_user"
]


def _source_choices(
    values: tuple[PackageSourceChoice, ...],
) -> tuple[PackageSourceChoice, ...]:
    if len(set(values)) != len(values):
        raise ValueError("Package sources must be unique")
    return tuple(sorted(values))


PackageSources = Annotated[
    tuple[PackageSourceChoice, ...],
    Field(min_length=1, max_length=3),
    AfterValidator(_source_choices),
]


class PackageSourceStatus(BaseModel):
    """Cached native observation, never an installation catalog or routing table."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    source: PackageSourceId
    updates: int = Field(ge=0)
    security_updates: int | None = Field(default=None, ge=0)
    scopes: tuple[Literal["full", "single", "selected"], ...]


class PackageInfo(BaseModel):
    """One normalized upgradable package row."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    name: str
    old_version: str
    new_version: str
    is_security: bool | None = False
    source: PackageSourceId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    display_name: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    scopes: tuple[Literal["full", "single", "selected"], ...] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class NativePackageVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    version: str


class PacmanReview(BaseModel):
    """Volatile package-solver candidates and unverified provenance observations."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    candidates: tuple[NativePackageVersion, ...]
    candidate_count: int = Field(ge=0)
    foreign: tuple[NativePackageVersion, ...]
    foreign_count: int = Field(ge=0)


class PackagesResponse(BaseModel):
    """Bounded package detail response with the unbounded parser count."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    packages: tuple[PackageInfo, ...]
    total: int
    sources: tuple[PackageSourceStatus, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    security_updates: int | None = 0
    checked_at: datetime | None
    provider: str | None
    pacman_review: PacmanReview | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class PackageUpdateRequest(BaseModel):
    """Exactly one explicit single-package or bounded selection scope."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    package_name: PackageName | None = None
    package_names: tuple[PackageName, ...] | None = Field(
        default=None, min_length=1, max_length=MAX_PACKAGE_DETAILS
    )

    @model_validator(mode="after")
    def validate_scope(self) -> PackageUpdateRequest:
        if (self.package_name is None) == (self.package_names is None):
            raise ValueError("Provide exactly one package scope")
        if self.package_names and len(set(self.package_names)) != len(
            self.package_names
        ):
            raise ValueError("Package selection must not contain duplicates")
        return self


class HostWebsite(BaseModel):
    """Operator-selected HTTP(S) shortcut; never fetched by the backend."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80)
    url: AnyHttpUrl = Field(max_length=2048)
    icon_url: AnyHttpUrl | None = Field(
        default=None, max_length=2048, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def reject_credentials(self) -> HostWebsite:
        for url in (self.url, self.icon_url):
            if url is not None and (
                url.username is not None or url.password is not None
            ):
                raise ValueError("Website links and icons must not include credentials")
        return self


class HostCreate(BaseModel):
    """Input accepted when registering a managed host."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: HostName
    address: HostAddress
    port: int = Field(default=22, ge=1, le=65535)
    username: SshUser
    package_provider: str = Field(default="debian_apt", pattern=r"^[a-z][a-z0-9_]+$")
    package_sources: PackageSources | None = None
    websites: tuple[HostWebsite, ...] = Field(default=(), max_length=12)


class HostPatch(BaseModel):
    """Fields that may be changed without changing host identity."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: HostName | None = None
    address: HostAddress | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    username: SshUser | None = None
    package_provider: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]+$")
    package_sources: PackageSources | None = None
    websites: tuple[HostWebsite, ...] | None = Field(default=None, max_length=12)


class Host(BaseModel):
    """Persisted host with stable UUID identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    name: str
    address: str
    port: int
    username: str
    package_provider: str
    package_sources: PackageSources | None = None
    package_observations: tuple[PackageSourceStatus, ...] = ()
    websites: tuple[HostWebsite, ...] = ()
    packages: tuple[PackageInfo, ...] = ()
    package_scopes: tuple[str, ...] | None = None
    distribution: str | None = None
    distribution_version: str | None = None
    kernel: str | None = None
    updates: int = 0
    security_updates: int | None = 0
    reboot_required: bool | None = False
    status: str | None = None
    checked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class HostListItem(BaseModel):
    """Host fields exposed by collection endpoints, without package details."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    name: str
    address: str
    port: int
    username: str
    package_provider: str
    package_sources: PackageSources | None = None
    package_observations: tuple[PackageSourceStatus, ...] = ()
    websites: tuple[HostWebsite, ...] = ()
    package_scopes: tuple[str, ...] | None = None
    distribution: str | None = None
    distribution_version: str | None = None
    kernel: str | None = None
    updates: int = 0
    security_updates: int | None = 0
    reboot_required: bool | None = False
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
    RESOURCE_OPERATION = "resource_operation"


class JobState(StrEnum):
    """Persistent queue lifecycle."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


_SHORT_JOB_ERRORS = {
    "execution_interrupted": (
        "Execution was interrupted; remote effects are uncertain. "
        "Inspect the resource before retrying."
    ),
    "execution_scope_changed": (
        "The execution target or task changed. Review and start a new job."
    ),
    "operation_not_permitted": (
        "The resource operation is unavailable or not authorized."
    ),
    "apt_lock_unavailable": "APT is locked by another process",
    "invalid_ansible_output": "Ansible returned an invalid structured result",
    "python_interpreter_unavailable": "Python 3 is not available on the host",
    "sudo_unavailable": "Non-interactive sudo is not available",
    "package_detection_failed": "Could not detect the target package environment",
    "package_source_unavailable": (
        "A selected native package source is unavailable. "
        "Check the host configuration and installed tools."
    ),
    "package_sources_partial_failure": (
        "A package source failed after an earlier source completed. "
        "Refresh native status and review the job before another update; "
        "no rollback or automatic retry was attempted."
    ),
    "package_provider_mismatch": (
        "The configured provider does not support this distribution, version or manager"
    ),
    "package_metadata_failed": (
        "Could not refresh package metadata; no update was started"
    ),
    "package_inventory_failed": "Could not collect package inventory",
    "package_selection_stale": (
        "The selected packages are no longer eligible; run a fresh check"
    ),
    "package_scope_unsupported": "This update scope is not supported on this host",
    "invalid_package_output": "The package manager returned an invalid inventory",
    "invalid_package_scope": "The package selection is invalid for this provider",
    "package_manager_restart_required": (
        "The package manager needs another reviewed invocation; no retry was performed"
    ),
}


class Job(BaseModel):
    """Persistent asynchronous job returned by the API."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    action: JobAction
    host_id: UUID | None
    host_name: str | None = None
    custom_task_id: UUID | None = None
    package_name: str | None = None
    package_names: tuple[str, ...] = ()
    state: JobState
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    exit_code: int | None = None
    error_code: str | None = None
    log_available: bool = False
    reviewed_at: datetime | None = None
    needs_review: bool = False
    reboot_required: bool | None = None

    execution: JobExecution | None = None
    interrupted_at: datetime | None = None
    interrupted_started_at: datetime | None = None
    recovery_count: int = 0

    # Mypy does not yet understand Pydantic's decorator above a property.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def job_id(self) -> UUID:
        """Expose the explicit API identity while retaining the v1 `id` field."""
        return self.id

    # Mypy does not yet understand Pydantic's decorator above a property.
    @computed_field(alias="type")  # type: ignore[prop-decorator]
    @property
    def job_type(self) -> JobAction:
        """Expose action semantics under the provider-neutral API name."""
        return self.action

    # Mypy does not yet understand Pydantic's decorator above a property.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def short_error(self) -> str | None:
        """Return a safe, bounded explanation without execution output."""
        if self.error_code is None:
            return None
        return _SHORT_JOB_ERRORS.get(
            self.error_code, self.error_code.replace("_", " ").capitalize()
        )

    # Mypy does not yet understand Pydantic's decorator above a property.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def duration(self) -> float | None:
        """Return terminal runtime in seconds when both timestamps exist."""
        if self.started_at is None or self.finished_at is None:
            return None
        return max(0.0, (self.finished_at - self.started_at).total_seconds())


class JobLog(BaseModel):
    """Bounded redacted output for one job."""

    job_id: UUID
    output: str
    truncated: bool


class CustomTaskMode(StrEnum):
    """Explicit execution semantics for a user-defined task."""

    COMMAND = "command"
    SHELL = "shell"


DependencyName = Annotated[str, Field(pattern=r"^[A-Za-z0-9_./+:-]{1,128}$")]
SystemName = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")]


class TaskRequirements(BaseModel):
    """Declarative, bounded prerequisites; never executable probe scripts."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    distributions: tuple[SystemName, ...] = Field(default=(), max_length=32)
    versions: tuple[Annotated[str, Field(pattern=r"^[0-9][0-9.]{0,31}$")], ...] = Field(
        default=(), max_length=32
    )
    programs: tuple[DependencyName, ...] = Field(default=(), max_length=32)
    packages: tuple[
        Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9+.:_-]{0,127}$")], ...
    ] = Field(default=(), max_length=32)
    requires_sudo: bool = False


class ProbeFacts(BaseModel):
    """Validated output of the fixed read-only execution adapter probe."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    distribution: str = Field(max_length=64)
    version: str = Field(max_length=64)
    missing_programs: tuple[DependencyName, ...] = Field(max_length=33)
    missing_packages: tuple[DependencyName, ...] = Field(max_length=32)


class CompatibilityState(StrEnum):
    UNCHECKED = "unchecked"
    SUITABLE = "suitable"
    UNSUITABLE = "unsuitable"
    FAILED = "failed"


class TaskCompatibility(BaseModel):
    """Safe metadata for one task/host pair, without raw command output."""

    model_config = ConfigDict(frozen=True)
    task_id: UUID
    host_id: UUID
    state: CompatibilityState = CompatibilityState.UNCHECKED
    reasons: tuple[str, ...] = ()
    checked_at: datetime | None = None
    assigned: bool = False
    enabled: bool = False


class AssignmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True


class CustomTaskCreate(BaseModel):
    """Validated custom task definition accepted by the API."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    mode: CustomTaskMode = CustomTaskMode.COMMAND
    argv: tuple[str, ...] | None = None
    shell_command: str | None = Field(default=None, max_length=4096)
    enabled: bool = True
    requirements: TaskRequirements = Field(default_factory=TaskRequirements)

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
    requirements: TaskRequirements = Field(default_factory=TaskRequirements)


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
    requirements: TaskRequirements = Field(default_factory=TaskRequirements)
    host_ids: tuple[UUID, ...] = ()
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


class UiLoginRequest(BaseModel):
    """One-time API-token input accepted only by standalone UI login."""

    model_config = ConfigDict(extra="forbid")

    api_token: str = Field(min_length=32, max_length=4096)


class UiSessionResponse(BaseModel):
    """Non-sensitive standalone UI authentication state."""

    authenticated: bool
