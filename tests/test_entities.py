"""Entity state, command, and diagnostic behavior tests."""

import json
from dataclasses import replace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
)
from homeassistant.components.button import (
    SERVICE_PRESS,
    ButtonDeviceClass,
)
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.components.update import SERVICE_INSTALL
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homelab_updates.diagnostics import (
    _safe_url,
    async_get_config_entry_diagnostics,
)
from custom_components.homelab_updates.domain import Command, HostStatus
from custom_components.homelab_updates.entity import async_start_command
from custom_components.homelab_updates.exceptions import (
    AuthenticationError,
    CannotConnectError,
    TaskAlreadyRunningError,
)

from .conftest import API_TOKEN, SEMAPHORE_URL
from .test_init import _setup_entry


async def test_entity_states_and_update_semantics(
    hass: HomeAssistant,
    aioclient_mock: object,
    mock_entry: MockConfigEntry,
) -> None:
    """Normalized host data appears through native Home Assistant states."""
    await _setup_entry(hass, aioclient_mock, mock_entry)

    update = hass.states.get("update.example_node_system_updates")
    assert update is not None
    assert update.state == "on"
    assert update.attributes["installed_version"] == "0"
    assert update.attributes["latest_version"] == "5"
    assert update.attributes["in_progress"] is False
    assert update.attributes["release_summary"] == "5 updates, 2 security updates"
    assert hass.states.get("sensor.example_node_available_updates").state == "5"  # type: ignore[union-attr]
    assert hass.states.get("sensor.example_node_security_updates").state == "2"  # type: ignore[union-attr]
    assert hass.states.get("sensor.example_node_kernel").state == "1.0.0-generic"  # type: ignore[union-attr]
    assert (
        hass.states.get("sensor.example_node_distribution").state == "Example Linux 1.0"
    )  # type: ignore[union-attr]
    assert (
        hass.states.get("sensor.example_node_last_check").state
        == "2026-01-15T12:00:00+00:00"
    )  # type: ignore[union-attr]
    assert hass.states.get("binary_sensor.example_node_reboot_required").state == "off"  # type: ignore[union-attr]


async def test_update_counts_zero_one_and_many(
    hass: HomeAssistant,
    aioclient_mock: object,
    mock_entry: MockConfigEntry,
    host_status: HostStatus,
) -> None:
    """Update availability is numeric and never lexical."""
    await _setup_entry(hass, aioclient_mock, mock_entry)
    runtime = mock_entry.runtime_data

    for updates, expected_state in ((0, "off"), (1, "on"), (41, "on")):
        changed = HostStatus(
            host_id=host_status.host_id,
            hostname=host_status.hostname,
            distribution=host_status.distribution,
            distribution_version=host_status.distribution_version,
            kernel=host_status.kernel,
            updates=updates,
            security_updates=99,
            reboot_required=host_status.reboot_required,
            status=host_status.status,
            checked_at=host_status.checked_at,
        )
        runtime.status_client.async_get_hosts = AsyncMock(  # type: ignore[method-assign]
            return_value={"node-01": changed}
        )
        await runtime.coordinator.async_refresh()
        await hass.async_block_till_done()
        state = hass.states.get("update.example_node_system_updates")
        assert state.state == expected_state  # type: ignore[union-attr]
        assert state.attributes["latest_version"] == str(updates)  # type: ignore[union-attr]


async def test_update_service_starts_host_limited_task(
    hass: HomeAssistant,
    aioclient_mock: object,
    mock_entry: MockConfigEntry,
) -> None:
    """The native install service delegates a host-limited update command."""
    await _setup_entry(hass, aioclient_mock, mock_entry)
    runtime = mock_entry.runtime_data
    runtime.task_manager._poll_interval = 0
    aioclient_mock.post(  # type: ignore[attr-defined]
        f"{SEMAPHORE_URL}/api/project/1/tasks", json={"id": 321}
    )
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{SEMAPHORE_URL}/api/project/1/tasks/321",
        json={"id": 321, "status": "success"},
    )

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.example_node_system_updates"},
        blocking=True,
    )
    await hass.async_block_till_done()

    post = next(call for call in aioclient_mock.mock_calls if call[0] == "POST")  # type: ignore[attr-defined]
    assert post[2] == {"template_id": 2, "limit": "node-01"}
    state = hass.states.get("update.example_node_system_updates")
    assert state.attributes["in_progress"] is False  # type: ignore[union-attr]


async def test_reboot_and_global_buttons_use_expected_targets(
    hass: HomeAssistant,
    aioclient_mock: object,
    mock_entry: MockConfigEntry,
) -> None:
    """Button actions choose reboot and check templates with correct limits."""
    await _setup_entry(hass, aioclient_mock, mock_entry)
    runtime = mock_entry.runtime_data
    runtime.task_manager._poll_interval = 0
    host = runtime.coordinator.data["node-01"]

    reboot_state = hass.states.get("button.example_node_reboot")
    assert reboot_state is not None
    assert reboot_state.state == "unavailable"

    runtime.coordinator.async_set_updated_data({
        "node-01": replace(host, reboot_required=True)
    })
    await hass.async_block_till_done()
    reboot_state = hass.states.get("button.example_node_reboot")
    assert reboot_state is not None
    assert reboot_state.state != "unavailable"
    assert reboot_state.attributes["device_class"] == ButtonDeviceClass.RESTART

    task_url = f"{SEMAPHORE_URL}/api/project/1/tasks"
    aioclient_mock.post(task_url, json={"id": 401})  # type: ignore[attr-defined]
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{task_url}/401", json={"id": 401, "status": "success"}
    )

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.example_node_reboot"},
        blocking=True,
    )
    await hass.async_block_till_done()
    first_post = next(call for call in aioclient_mock.mock_calls if call[0] == "POST")  # type: ignore[attr-defined]
    assert first_post[2] == {"template_id": 3, "limit": "node-01"}

    aioclient_mock.clear_requests()  # type: ignore[attr-defined]
    aioclient_mock.post(task_url, json={"id": 402})  # type: ignore[attr-defined]
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{task_url}/402", json={"id": 402, "status": "success"}
    )
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.homelab_commander_check_all_hosts"},
        blocking=True,
    )
    await hass.async_block_till_done()
    second_post = next(call for call in aioclient_mock.mock_calls if call[0] == "POST")  # type: ignore[attr-defined]
    assert second_post[2] == {"template_id": 1}


async def test_diagnostics_are_allowlisted_and_redacted(
    hass: HomeAssistant,
    aioclient_mock: object,
    mock_entry: MockConfigEntry,
) -> None:
    """Diagnostics expose health counters but no token or host identity."""
    await _setup_entry(hass, aioclient_mock, mock_entry)

    diagnostics = await async_get_config_entry_diagnostics(
        hass,
        mock_entry,
    )
    serialized = json.dumps(diagnostics)

    assert API_TOKEN not in serialized
    assert "node-01" not in serialized
    assert diagnostics["runtime"]["host_count"] == 1
    assert diagnostics["config"]["api_token"] == "**REDACTED**"


def test_diagnostic_url_redaction() -> None:
    """Credentials, queries, and fragments never appear in diagnostics."""
    assert (
        _safe_url("https://user:secret@service.example.invalid/status?token=x#part")
        == "https://service.example.invalid/status"
    )


@pytest.mark.parametrize(
    "error",
    [AuthenticationError(), TaskAlreadyRunningError(), CannotConnectError()],
)
async def test_entity_command_errors_are_safe(error: Exception) -> None:
    """Application errors become localized Home Assistant service errors."""
    manager = Mock()
    manager.async_start = AsyncMock(side_effect=error)
    with pytest.raises(HomeAssistantError):
        await async_start_command(manager, Command.CHECK_ALL)
