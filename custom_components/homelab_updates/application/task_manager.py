"""Lifecycle-aware asynchronous task tracking."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import timedelta

from homeassistant.core import HomeAssistant

from ..const import DEFAULT_TASK_POLL_INTERVAL, DEFAULT_TASK_TIMEOUT
from ..domain import BackendTask, Command, TaskId, TaskPhase
from ..exceptions import (
    AuthenticationError,
    BackendTaskError,
    CannotConnectError,
    HomelabUpdatesError,
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
        self._states: dict[str, BackendTask] = {}
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
    ) -> BackendTask | None:
        """Return the most recently known state for a command."""
        return self._states.get(command.key(host_id))

    @property
    def active_task_count(self) -> int:
        """Return the number of currently active tasks."""
        return sum(not task.done() for task in self._tasks.values())

    async def async_start(
        self, command: Command, host_id: str | None = None
    ) -> BackendTask:
        """Start a command and track it in the background."""
        key = command.key(host_id)
        if self.is_running(command, host_id):
            raise TaskAlreadyRunningError("This command is already running")

        try:
            started = await self._async_dispatch(command, host_id)
        except AuthenticationError:
            self._auth_failure_callback()
            raise

        self._states[key] = started
        tracker = self._hass.async_create_task(
            self._async_track(key, started.task_id),
            f"Track Homelab Commander task {started.task_id}",
        )
        self._tasks[key] = tracker
        tracker.add_done_callback(
            lambda completed: self._async_tracker_done(key, completed)
        )
        self._notify_listeners()
        return started

    async def async_start_custom(self, task_id: str, host_id: str) -> BackendTask:
        """Start one backend-defined task for exactly one host."""
        key = self._custom_key(task_id, host_id)
        running = self._tasks.get(key)
        if running is not None and not running.done():
            raise TaskAlreadyRunningError("This custom task is already running")
        try:
            started = await self._backend.async_run_task(task_id, host_id)
        except AuthenticationError:
            self._auth_failure_callback()
            raise
        self._states[key] = started
        tracker = self._hass.async_create_task(
            self._async_track(key, started.task_id),
            f"Track Homelab Commander task {started.task_id}",
        )
        self._tasks[key] = tracker
        tracker.add_done_callback(
            lambda completed: self._async_tracker_done(key, completed)
        )
        self._notify_listeners()
        return started

    def is_custom_running(self, task_id: str, host_id: str) -> bool:
        """Return whether one custom task/host combination is active."""
        task = self._tasks.get(self._custom_key(task_id, host_id))
        return task is not None and not task.done()

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
        task_id: TaskId,
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
                    await self._refresh_callback()
                    return
                if task.phase in {TaskPhase.FAILED, TaskPhase.CANCELLED}:
                    await self._refresh_callback()
                    raise BackendTaskError(
                        f"Automation task {task_id} failed for {key}"
                    )
                await asyncio.sleep(self._poll_interval)

            reason = " after backend connection errors" if had_connection_error else ""
            raise BackendTaskError(f"Automation task {task_id} timed out{reason}")
        except asyncio.CancelledError:
            raise
        except HomelabUpdatesError as err:
            current = self._states.get(key)
            if current is None or current.phase not in {
                TaskPhase.FAILED,
                TaskPhase.CANCELLED,
            }:
                self._states[key] = BackendTask(
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

    def _async_tracker_done(self, key: str, completed: asyncio.Task[None]) -> None:
        """Remove one completed tracker and publish the final idle state."""
        if self._tasks.get(key) is not completed:
            return
        self._tasks.pop(key)
        self._notify_listeners()

    async def _async_dispatch(
        self, command: Command, host_id: str | None
    ) -> BackendTask:
        """Dispatch a command through provider-neutral backend capabilities."""
        if command is Command.CHECK_ALL:
            if host_id is not None:
                raise BackendTaskError("This command does not accept a host")
            return await self._backend.async_check_hosts()
        if command is Command.REFRESH_STATUS:
            if host_id is not None:
                raise BackendTaskError("This command does not accept a host")
            return await self._backend.async_refresh_hosts()
        if host_id is None:
            raise BackendTaskError("This command requires a host")
        if command is Command.UPDATE_HOST:
            return await self._backend.async_update_host(host_id)
        return await self._backend.async_reboot_host(host_id)

    @staticmethod
    def _custom_key(task_id: str, host_id: str) -> str:
        return f"custom:{task_id}:{host_id}"
