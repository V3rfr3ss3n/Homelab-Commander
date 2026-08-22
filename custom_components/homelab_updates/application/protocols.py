"""Ports implemented by infrastructure adapters."""

from collections.abc import Mapping, Sequence
from typing import Protocol

from ..domain import (
    BackendJobLog,
    BackendTask,
    CustomTaskDefinition,
    HostStatus,
    TaskId,
)


class HostProvider(Protocol):
    """Read-only source of normalized host status."""

    async def async_get_hosts(self) -> Mapping[str, HostStatus]:
        """Fetch one complete host snapshot."""

    async def async_validate(self) -> None:
        """Validate connectivity and payload structure."""


class AutomationBackend(Protocol):
    """Backend capable of executing explicit maintenance commands."""

    async def async_validate(self) -> None:
        """Validate authentication and project access."""

    async def async_check_hosts(self) -> BackendTask:
        """Queue a read-only status collection for all hosts."""

    async def async_refresh_hosts(self) -> BackendTask:
        """Queue a refresh of the backend's host snapshot."""

    async def async_update_host(self, host_id: str) -> BackendTask:
        """Queue an update for exactly one host."""

    async def async_reboot_host(self, host_id: str) -> BackendTask:
        """Queue a reboot for exactly one host."""

    async def async_run_task(self, task_id: str, host_id: str) -> BackendTask:
        """Queue a configured custom task for exactly one host."""

    async def async_get_task(self, task_id: TaskId) -> BackendTask:
        """Fetch the current state of one task."""

    async def async_get_tasks(self) -> Sequence[BackendTask]:
        """Fetch recent tasks visible to this backend."""

    async def async_get_job_log(self, job_id: str) -> BackendJobLog:
        """Fetch one authenticated, bounded backend job log on demand."""

    async def async_get_custom_tasks(self) -> Sequence[CustomTaskDefinition]:
        """Fetch custom actions exposed by this backend."""


# Compatibility name for code written against the 0.1 port.
StatusProvider = HostProvider
