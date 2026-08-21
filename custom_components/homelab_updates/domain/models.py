"""Transport-independent domain models."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class HostStatus:
    """Normalized status for one managed host."""

    host_id: str
    hostname: str | None
    distribution: str | None
    distribution_version: str | None
    kernel: str | None
    updates: int
    security_updates: int
    reboot_required: bool
    status: str | None
    checked_at: datetime

    @property
    def display_name(self) -> str:
        """Return a friendly but identity-independent display name."""
        return self.hostname or self.host_id

    @property
    def distribution_display(self) -> str | None:
        """Return distribution and version as one compact value."""
        values = tuple(
            value for value in (self.distribution, self.distribution_version) if value
        )
        return " ".join(values) or None


class TaskPhase(StrEnum):
    """Normalized lifecycle phase of an automation task."""

    WAITING = "waiting"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SemaphoreTask:
    """Normalized automation task returned by a backend."""

    task_id: int
    phase: TaskPhase
    raw_status: str


class Command(StrEnum):
    """Application-level command capability."""

    CHECK_ALL = "check_all"
    REFRESH_STATUS = "refresh_status"
    UPDATE_HOST = "update_host"
    REBOOT_HOST = "reboot_host"

    def key(self, host_id: str | None = None) -> str:
        """Return the concurrency and listener key for this command."""
        return f"{self.value}:{host_id}" if host_id is not None else self.value
