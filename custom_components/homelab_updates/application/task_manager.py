"""Lifecycle-aware asynchronous task tracking."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import timedelta

from homeassistant.core import HomeAssistant

from ..const import DEFAULT_TASK_POLL_INTERVAL, DEFAULT_TASK_TIMEOUT
from ..domain import Command, SemaphoreTask, TaskPhase
from ..exceptions import (
    AuthenticationError,
    CannotConnectError,
    HomelabUpdatesError,
    SemaphoreTaskError,
    TaskAlreadyRunningError,
)
from .protocols import AutomationBackend

_LOGGER = logging.getLogger(__name__)

TaskListener = Callable[[], None]
RefreshCallback = Callable[[], Awaitable[None]]
AuthFailureCallback = Callable[[], None]


class TaskManager:
    """Start, track, and cancel backend tasks without blocking Home Assistant."""

    def __init__(
        self,
        hass: HomeAssistant,
        backend: AutomationBackend,
        refresh_callback: RefreshCallback,
        auth_failure_callback: AuthFailureCallback,
        *,
        poll_interval: float = DEFAULT_TASK_POLL_INTERVAL,
        task_timeout: timedelta = DEFAULT_TASK_TIMEOUT,
    ) -> None:
        """Initialize the task manager."""
        self._hass = hass
        self._backend = backend
        self._refresh_callback = refresh_callback
        self._auth_failure_callback = auth_failure_callback
        self._poll_interval = poll_interval
        self._task_timeout = task_timeout
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._states: dict[str, SemaphoreTask] = {}
        self._listeners: set[TaskListener] = set()

    def async_add_listener(self, listener: TaskListener) -> Callable[[], None]:
        """Register a state listener and return its unsubscribe callback."""
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def is_running(self, command: Command, host_id: str | None = None) -> bool:
        """Return whether a command is currently tracked as active."""
        task = self._tasks.get(command.key(host_id))
        return task is not None and not task.done()

    def task_state(
        self, command: Command, host_id: str | None = None
    ) -> SemaphoreTask | None:
        """Return the most recently known state for a command."""
        return self._states.get(command.key(host_id))

    @property
    def active_task_count(self) -> int:
        """Return the number of currently active tasks."""
        return sum(not task.done() for task in self._tasks.values())

    async def async_start(
        self, command: Command, host_id: str | None = None
    ) -> SemaphoreTask:
        """Start a command and track it in the background."""
        key = command.key(host_id)
        if self.is_running(command, host_id):
            raise TaskAlreadyRunningError("This command is already running")

        try:
            started = await self._backend.async_start_command(command, host_id)
        except AuthenticationError:
            self._auth_failure_callback()
            raise

        self._states[key] = started
        self._notify_listeners()
        tracker = self._hass.async_create_task(
            self._async_track(key, command, host_id, started.task_id),
            f"Track Homelab Updates task {started.task_id}",
        )
        self._tasks[key] = tracker
        tracker.add_done_callback(lambda _task: self._tasks.pop(key, None))
        return started

    async def async_cancel(self) -> None:
        """Cancel all tracking tasks during config entry unload."""
        tasks = tuple(self._tasks.values())
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()
        self._listeners.clear()

    async def _async_track(
        self,
        key: str,
        command: Command,
        host_id: str | None,
        task_id: int,
    ) -> None:
        """Poll one task until completion, cancellation, or timeout."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._task_timeout.total_seconds()
        had_connection_error = False

        try:
            await asyncio.sleep(self._poll_interval)
            while loop.time() < deadline:
                try:
                    task = await self._backend.async_get_task(task_id)
                    had_connection_error = False
                except AuthenticationError:
                    self._auth_failure_callback()
                    raise
                except CannotConnectError:
                    had_connection_error = True
                    await asyncio.sleep(self._poll_interval)
                    continue

                self._states[key] = task
                self._notify_listeners()
                if task.phase is TaskPhase.SUCCESS:
                    if command in {
                        Command.CHECK_ALL,
                        Command.REFRESH_STATUS,
                        Command.UPDATE_HOST,
                    }:
                        await self._refresh_callback()
                    return
                if task.phase is TaskPhase.FAILED:
                    raise SemaphoreTaskError(
                        f"Automation task {task_id} failed for {key}"
                    )
                await asyncio.sleep(self._poll_interval)

            reason = " after backend connection errors" if had_connection_error else ""
            raise SemaphoreTaskError(f"Automation task {task_id} timed out{reason}")
        except asyncio.CancelledError:
            raise
        except HomelabUpdatesError as err:
            self._states[key] = SemaphoreTask(
                task_id=task_id,
                phase=TaskPhase.FAILED,
                raw_status="failed",
            )
            self._notify_listeners()
            _LOGGER.error("Task %s failed for command %s: %s", task_id, key, err)
        finally:
            self._notify_listeners()

    def _notify_listeners(self) -> None:
        """Notify a stable snapshot of listeners."""
        for listener in tuple(self._listeners):
            listener()
