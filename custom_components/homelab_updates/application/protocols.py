"""Ports implemented by infrastructure adapters."""

from collections.abc import Mapping
from typing import Protocol

from ..domain import Command, HostStatus, SemaphoreTask


class StatusProvider(Protocol):
    """Read-only source of normalized host status."""

    async def async_get_hosts(self) -> Mapping[str, HostStatus]:
        """Fetch one complete host snapshot."""

    async def async_validate(self) -> None:
        """Validate connectivity and payload structure."""


class AutomationBackend(Protocol):
    """Backend capable of executing explicit maintenance commands."""

    async def async_validate(self) -> None:
        """Validate authentication and project access."""

    async def async_start_command(
        self, command: Command, host_id: str | None = None
    ) -> SemaphoreTask:
        """Start a command and return its task."""

    async def async_get_task(self, task_id: int) -> SemaphoreTask:
        """Fetch the current state of a task."""
