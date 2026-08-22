"""Coordinator and task lifecycle tests."""

import asyncio
import logging
from datetime import timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.homelab_updates.application.task_manager import TaskManager
from custom_components.homelab_updates.coordinator import HomelabUpdatesCoordinator
from custom_components.homelab_updates.domain import (
    BackendTask,
    Command,
    HostStatus,
    TaskPhase,
)
from custom_components.homelab_updates.exceptions import (
    AuthenticationError,
    BackendTaskError,
    CannotConnectError,
    TaskAlreadyRunningError,
)


async def test_coordinator_loads_snapshot(
    hass: HomeAssistant,
    host_status: HostStatus,
) -> None:
    """The coordinator copies one complete provider snapshot."""
    provider = Mock()
    provider.async_get_hosts = AsyncMock(return_value={"node-01": host_status})
    coordinator = HomelabUpdatesCoordinator(hass, provider, timedelta(minutes=5))

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.data == {"node-01": host_status}
    provider.async_get_hosts.assert_awaited_once()


async def test_coordinator_failure_is_update_failed(hass: HomeAssistant) -> None:
    """Provider errors make a refresh unsuccessful without escaping."""
    provider = Mock()
    provider.async_get_hosts = AsyncMock(side_effect=CannotConnectError())
    coordinator = HomelabUpdatesCoordinator(hass, provider, timedelta(minutes=5))

    await coordinator.async_refresh()

    assert not coordinator.last_update_success


def _task(task_id: int | str, phase: TaskPhase) -> BackendTask:
    return BackendTask(task_id=task_id, phase=phase, raw_status=phase.value)


async def test_task_manager_tracks_success_and_refreshes(
    hass: HomeAssistant,
) -> None:
    """Successful status-changing commands trigger exactly one refresh."""
    backend = Mock()
    backend.async_update_host = AsyncMock(return_value=_task(123, TaskPhase.WAITING))
    backend.async_get_task = AsyncMock(return_value=_task(123, TaskPhase.SUCCESS))
    refresh = AsyncMock()
    manager = TaskManager(
        hass,
        backend,
        refresh,
        Mock(),
        poll_interval=0,
        task_timeout=timedelta(seconds=1),
    )
    listener = Mock()
    remove_listener = manager.async_add_listener(listener)

    started = await manager.async_start(Command.UPDATE_HOST, "node-01")
    assert started.task_id == 123
    assert manager.is_running(Command.UPDATE_HOST, "node-01")
    await hass.async_block_till_done()

    assert manager.task_state(Command.UPDATE_HOST, "node-01").phase is TaskPhase.SUCCESS  # type: ignore[union-attr]
    refresh.assert_awaited_once()
    assert listener.call_count >= 2
    remove_listener()
    await manager.async_cancel()


async def test_task_manager_reboot_refreshes_job_observability(
    hass: HomeAssistant,
) -> None:
    """A reboot completion refreshes job and host observability once."""
    backend = Mock()
    backend.async_reboot_host = AsyncMock(return_value=_task(124, TaskPhase.WAITING))
    backend.async_get_task = AsyncMock(return_value=_task(124, TaskPhase.SUCCESS))
    refresh = AsyncMock()
    manager = TaskManager(
        hass,
        backend,
        refresh,
        Mock(),
        poll_interval=0,
        task_timeout=timedelta(seconds=1),
    )
    await manager.async_start(Command.REBOOT_HOST, "node-01")
    await hass.async_block_till_done()
    refresh.assert_awaited_once()


async def test_task_manager_failure_is_recorded(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Backend task failure clears progress and records a safe task ID."""
    backend = Mock()
    backend.async_check_hosts = AsyncMock(return_value=_task(125, TaskPhase.WAITING))
    backend.async_get_task = AsyncMock(return_value=_task(125, TaskPhase.FAILED))
    refresh = AsyncMock()
    manager = TaskManager(
        hass,
        backend,
        refresh,
        Mock(),
        poll_interval=0,
        task_timeout=timedelta(seconds=1),
    )
    with caplog.at_level(logging.ERROR):
        await manager.async_start(Command.CHECK_ALL)
        await hass.async_block_till_done()

    assert manager.task_state(Command.CHECK_ALL).phase is TaskPhase.FAILED  # type: ignore[union-attr]
    refresh.assert_awaited_once()
    assert "125" in caplog.text
    assert "synthetic-test-token" not in caplog.text


async def test_task_manager_cancelled_job_refreshes_and_stops_tracking(
    hass: HomeAssistant,
) -> None:
    """Cancelled is terminal and refreshes the observable history."""
    backend = Mock()
    backend.async_check_hosts = AsyncMock(return_value=_task(225, TaskPhase.WAITING))
    backend.async_get_task = AsyncMock(return_value=_task(225, TaskPhase.CANCELLED))
    refresh = AsyncMock()
    manager = TaskManager(
        hass,
        backend,
        refresh,
        Mock(),
        poll_interval=0,
        task_timeout=timedelta(seconds=1),
    )

    await manager.async_start(Command.CHECK_ALL)
    await hass.async_block_till_done()

    refresh.assert_awaited_once()
    assert manager.task_state(Command.CHECK_ALL).phase is TaskPhase.CANCELLED  # type: ignore[union-attr]


async def test_task_manager_rejects_duplicate(hass: HomeAssistant) -> None:
    """The same host command cannot be started twice concurrently."""
    release = asyncio.Event()

    async def _wait_for_task(task_id: int | str) -> BackendTask:
        await release.wait()
        return _task(task_id, TaskPhase.SUCCESS)

    backend = Mock()
    backend.async_update_host = AsyncMock(return_value=_task(126, TaskPhase.WAITING))
    backend.async_get_task = AsyncMock(side_effect=_wait_for_task)
    manager = TaskManager(
        hass,
        backend,
        AsyncMock(),
        Mock(),
        poll_interval=0,
        task_timeout=timedelta(seconds=1),
    )
    await manager.async_start(Command.UPDATE_HOST, "node-01")
    with pytest.raises(TaskAlreadyRunningError):
        await manager.async_start(Command.UPDATE_HOST, "node-01")
    release.set()
    await hass.async_block_till_done()


async def test_task_manager_starts_reauth_on_auth_failure(
    hass: HomeAssistant,
) -> None:
    """An immediate authentication failure requests Home Assistant reauth."""
    backend = Mock()
    backend.async_check_hosts = AsyncMock(side_effect=AuthenticationError())
    reauth = Mock()
    manager = TaskManager(hass, backend, AsyncMock(), reauth)

    with pytest.raises(AuthenticationError):
        await manager.async_start(Command.CHECK_ALL)

    reauth.assert_called_once()


async def test_task_manager_recovers_from_poll_connection_error(
    hass: HomeAssistant,
) -> None:
    """A transient polling failure is retried until the task succeeds."""
    backend = Mock()
    backend.async_refresh_hosts = AsyncMock(return_value=_task(127, TaskPhase.WAITING))
    backend.async_get_task = AsyncMock(
        side_effect=[CannotConnectError(), _task(127, TaskPhase.SUCCESS)]
    )
    refresh = AsyncMock()
    manager = TaskManager(
        hass,
        backend,
        refresh,
        Mock(),
        poll_interval=0,
        task_timeout=timedelta(seconds=1),
    )
    await manager.async_start(Command.REFRESH_STATUS)
    await hass.async_block_till_done()
    refresh.assert_awaited_once()


async def test_task_manager_poll_auth_failure_requests_reauth(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Authentication loss during tracking records failure and starts reauth."""
    backend = Mock()
    backend.async_check_hosts = AsyncMock(return_value=_task(128, TaskPhase.WAITING))
    backend.async_get_task = AsyncMock(side_effect=AuthenticationError())
    reauth = Mock()
    manager = TaskManager(
        hass,
        backend,
        AsyncMock(),
        reauth,
        poll_interval=0,
        task_timeout=timedelta(seconds=1),
    )
    with caplog.at_level(logging.ERROR):
        await manager.async_start(Command.CHECK_ALL)
        await hass.async_block_till_done()
    reauth.assert_called_once()
    assert manager.task_state(Command.CHECK_ALL).phase is TaskPhase.FAILED  # type: ignore[union-attr]


async def test_task_manager_cancels_active_tracker(hass: HomeAssistant) -> None:
    """Unload cancellation awaits and removes an active polling task."""
    release = asyncio.Event()

    async def _blocked(task_id: int | str) -> BackendTask:
        await release.wait()
        return _task(task_id, TaskPhase.SUCCESS)

    backend = Mock()
    backend.async_check_hosts = AsyncMock(return_value=_task(129, TaskPhase.WAITING))
    backend.async_get_task = AsyncMock(side_effect=_blocked)
    manager = TaskManager(
        hass,
        backend,
        AsyncMock(),
        Mock(),
        poll_interval=0,
    )
    await manager.async_start(Command.CHECK_ALL)
    await asyncio.sleep(0)
    await manager.async_cancel()
    assert manager.active_task_count == 0


async def test_task_manager_timeout_is_recorded(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A zero task deadline terminates deterministically as failed."""
    backend = Mock()
    backend.async_check_hosts = AsyncMock(return_value=_task(130, TaskPhase.WAITING))
    backend.async_get_task = AsyncMock()
    manager = TaskManager(
        hass,
        backend,
        AsyncMock(),
        Mock(),
        poll_interval=0,
        task_timeout=timedelta(0),
    )
    with caplog.at_level(logging.ERROR):
        await manager.async_start(Command.CHECK_ALL)
        await hass.async_block_till_done()
    assert "timed out" in caplog.text
    assert manager.task_state(Command.CHECK_ALL).phase is TaskPhase.FAILED  # type: ignore[union-attr]


async def test_task_manager_rejects_missing_or_unexpected_target(
    hass: HomeAssistant,
) -> None:
    """Mutations fail closed and global commands cannot gain a hidden target."""
    backend = Mock()
    manager = TaskManager(hass, backend, AsyncMock(), Mock())

    with pytest.raises(BackendTaskError, match="requires a host"):
        await manager.async_start(Command.REBOOT_HOST)
    with pytest.raises(BackendTaskError, match="does not accept a host"):
        await manager.async_start(Command.CHECK_ALL, "node-01")

    assert not backend.mock_calls


async def test_task_manager_supports_opaque_backend_task_ids(
    hass: HomeAssistant,
) -> None:
    """Native backends can use stable UUID strings as task identifiers."""
    task_id = "00000000-0000-4000-8000-000000000001"
    backend = Mock()
    backend.async_check_hosts = AsyncMock(
        return_value=_task(task_id, TaskPhase.WAITING)
    )
    backend.async_get_task = AsyncMock(return_value=_task(task_id, TaskPhase.SUCCESS))
    manager = TaskManager(
        hass,
        backend,
        AsyncMock(),
        Mock(),
        poll_interval=0,
        task_timeout=timedelta(seconds=1),
    )

    assert (await manager.async_start(Command.CHECK_ALL)).task_id == task_id
    await hass.async_block_till_done()
    backend.async_get_task.assert_awaited_once_with(task_id)


async def test_task_manager_tracks_custom_task_by_task_and_host(
    hass: HomeAssistant,
) -> None:
    """Custom task concurrency keys cannot collide across task definitions."""
    task_id = "00000000-0000-4000-8000-000000000004"
    job_id = "00000000-0000-4000-8000-000000000005"
    backend = Mock()
    backend.async_run_task = AsyncMock(return_value=_task(job_id, TaskPhase.WAITING))
    backend.async_get_task = AsyncMock(return_value=_task(job_id, TaskPhase.SUCCESS))
    refresh = AsyncMock()
    manager = TaskManager(
        hass,
        backend,
        refresh,
        Mock(),
        poll_interval=0,
        task_timeout=timedelta(seconds=1),
    )

    await manager.async_start_custom(task_id, "node-01")
    assert manager.is_custom_running(task_id, "node-01")
    await hass.async_block_till_done()

    backend.async_run_task.assert_awaited_once_with(task_id, "node-01")
    refresh.assert_awaited_once()
