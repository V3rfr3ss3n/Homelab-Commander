"""Config entry lifecycle and dynamic entity integration tests."""

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homelab_updates import _async_reload_entry, async_unload_entry
from custom_components.homelab_updates.const import DOMAIN
from custom_components.homelab_updates.domain import HostStatus

from .conftest import STATUS_URL
from .test_api import _payload


async def _setup_entry(
    hass: HomeAssistant,
    aioclient_mock: object,
    entry: MockConfigEntry,
) -> None:
    aioclient_mock.get(STATUS_URL, json=_payload())  # type: ignore[attr-defined]
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_creates_devices_and_entities(
    hass: HomeAssistant,
    aioclient_mock: object,
    mock_entry: MockConfigEntry,
) -> None:
    """One discovered host creates a device entity set and two hub actions."""
    await _setup_entry(hass, aioclient_mock, mock_entry)

    entities = [
        entity
        for entity in er.async_get(hass).entities.values()
        if entity.config_entry_id == mock_entry.entry_id
    ]
    assert len(entities) == 10
    unique_ids = {entity.unique_id for entity in entities}
    assert f"{DOMAIN}_node-01_system_update" in unique_ids
    assert f"{DOMAIN}_node-01_available_updates" in unique_ids
    assert f"{DOMAIN}_node-01_security_updates" in unique_ids
    assert f"{DOMAIN}_node-01_kernel" in unique_ids
    assert f"{DOMAIN}_node-01_distribution" in unique_ids
    assert f"{DOMAIN}_node-01_last_check" in unique_ids
    assert f"{DOMAIN}_node-01_reboot_required" in unique_ids
    assert f"{DOMAIN}_node-01_reboot" in unique_ids

    devices = [
        device
        for device in dr.async_get(hass).devices.values()
        if mock_entry.entry_id in device.config_entries
    ]
    assert len(devices) == 2
    assert {device.name for device in devices} == {
        "example-node",
        "Homelab Updates",
    }


async def test_new_host_is_added_dynamically(
    hass: HomeAssistant,
    aioclient_mock: object,
    mock_entry: MockConfigEntry,
    host_status: HostStatus,
) -> None:
    """A later host snapshot adds entities without reloading the entry."""
    await _setup_entry(hass, aioclient_mock, mock_entry)
    runtime = mock_entry.runtime_data
    second_host = HostStatus(
        host_id="node-02",
        hostname=None,
        distribution=host_status.distribution,
        distribution_version=host_status.distribution_version,
        kernel=host_status.kernel,
        updates=0,
        security_updates=0,
        reboot_required=True,
        status="ok",
        checked_at=host_status.checked_at,
    )
    runtime.status_client.async_get_hosts = AsyncMock(  # type: ignore[method-assign]
        return_value={"node-01": host_status, "node-02": second_host}
    )

    await runtime.coordinator.async_refresh()
    await hass.async_block_till_done()

    entities = [
        entity
        for entity in er.async_get(hass).entities.values()
        if entity.config_entry_id == mock_entry.entry_id
    ]
    assert len(entities) == 18
    assert f"{DOMAIN}_node-02_system_update" in {
        entity.unique_id for entity in entities
    }


async def test_missing_host_becomes_unavailable_without_registry_removal(
    hass: HomeAssistant,
    aioclient_mock: object,
    mock_entry: MockConfigEntry,
) -> None:
    """A missing host keeps its registry entries and becomes unavailable."""
    await _setup_entry(hass, aioclient_mock, mock_entry)
    runtime = mock_entry.runtime_data
    registry = er.async_get(hass)
    update_entry = next(
        entity
        for entity in registry.entities.values()
        if entity.unique_id == f"{DOMAIN}_node-01_system_update"
    )
    runtime.status_client.async_get_hosts = AsyncMock(return_value={})  # type: ignore[method-assign]

    await runtime.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert registry.async_get(update_entry.entity_id) is not None
    assert hass.states.get(update_entry.entity_id).state == "unavailable"  # type: ignore[union-attr]


async def test_unload_removes_states_and_cancels_runtime(
    hass: HomeAssistant,
    aioclient_mock: object,
    mock_entry: MockConfigEntry,
) -> None:
    """Config entry unload removes platform states cleanly."""
    await _setup_entry(hass, aioclient_mock, mock_entry)
    entity_ids = {
        entity.entity_id
        for entity in er.async_get(hass).entities.values()
        if entity.config_entry_id == mock_entry.entry_id
    }

    assert await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()

    remaining_states = {
        state.state
        for entity_id in entity_ids
        if (state := hass.states.get(entity_id)) is not None
    }
    assert remaining_states <= {"unavailable"}


async def test_unload_failure_and_reload_delegate_to_home_assistant(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
) -> None:
    """Lifecycle helpers preserve platform failure and delegate reload by ID."""
    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=False),
    ):
        assert not await async_unload_entry(hass, mock_entry)
    with patch.object(
        hass.config_entries,
        "async_reload",
        AsyncMock(),
    ) as reload_mock:
        await _async_reload_entry(hass, mock_entry)
    reload_mock.assert_awaited_once_with(mock_entry.entry_id)
