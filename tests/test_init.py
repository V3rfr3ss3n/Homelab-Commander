"""Config entry lifecycle and dynamic entity integration tests."""

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homelab_updates import (
    _async_reload_entry,
    async_migrate_entry,
    async_unload_entry,
)
from custom_components.homelab_updates.const import (
    BACKEND_NATIVE,
    BACKEND_SEMAPHORE,
    CONF_BACKEND_TYPE,
    CONF_BACKEND_URL,
    CONF_POLL_INTERVAL,
    CONF_VERIFY_SSL,
    DOMAIN,
)
from custom_components.homelab_updates.domain import HostStatus

from .conftest import API_TOKEN, STATUS_URL
from .test_api import (
    HOST_ID,
    NATIVE_URL,
    _native_host_payload,
    _native_job_payload,
    _payload,
)


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


async def test_version_one_entry_migrates_to_semaphore_provider(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """Existing users keep their provider and all connection settings."""
    mock_entry.add_to_hass(hass)
    original = dict(mock_entry.data)

    assert await async_migrate_entry(hass, mock_entry)  # type: ignore[arg-type]

    assert mock_entry.version == 2
    assert mock_entry.minor_version == 1
    assert mock_entry.data == {
        **original,
        CONF_BACKEND_TYPE: BACKEND_SEMAPHORE,
    }


async def test_native_setup_creates_job_and_health_entities(
    hass: HomeAssistant, aioclient_mock: object
) -> None:
    """Native entries expose host entities plus provider-neutral job telemetry."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/hosts", json=[_native_host_payload()]
    )
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/jobs", json=[]
    )
    task_id = "00000000-0000-4000-8000-000000000004"
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/custom-tasks",
        json=[
            {
                "id": task_id,
                "name": "Synthetic task",
                "description": "No real command",
                "enabled": True,
            }
        ],
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="backend.example.invalid",
        version=2,
        minor_version=1,
        unique_id=f"native|{NATIVE_URL}",
        data={
            CONF_BACKEND_TYPE: BACKEND_NATIVE,
            CONF_BACKEND_URL: NATIVE_URL,
            "api_token": API_TOKEN,
            CONF_POLL_INTERVAL: 300,
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    unique_ids = {
        entity.unique_id
        for entity in er.async_get(hass).entities.values()
        if entity.config_entry_id == entry.entry_id
    }
    assert len(unique_ids) == 19
    assert f"{DOMAIN}_{HOST_ID}_last_job" in unique_ids
    assert f"{DOMAIN}_{HOST_ID}_last_failed_job" in unique_ids
    assert f"{DOMAIN}_{entry.entry_id}_backend_health" in unique_ids
    assert f"{DOMAIN}_{entry.entry_id}_queued_jobs" in unique_ids
    assert f"{DOMAIN}_{entry.entry_id}_running_jobs" in unique_ids
    assert f"{DOMAIN}_{entry.entry_id}_last_job" in unique_ids
    assert f"{DOMAIN}_{entry.entry_id}_last_job_type" in unique_ids
    assert f"{DOMAIN}_{entry.entry_id}_last_failed_job" in unique_ids
    assert f"{DOMAIN}_{HOST_ID}_custom_task_{task_id}" in unique_ids


async def test_native_job_entities_separate_current_success_from_old_failure(
    hass: HomeAssistant, aioclient_mock: object
) -> None:
    """A historical failure never masquerades as current backend or job health."""
    failed_id = "00000000-0000-4000-8000-000000000003"
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/hosts", json=[_native_host_payload()]
    )
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/jobs",
        json=[
            _native_job_payload(
                action="check_updates",
                state="success",
                host_name="Node 01",
                started_at="2026-01-15T21:39:00Z",
                finished_at="2026-01-15T21:40:00Z",
                exit_code=0,
                duration=60,
                log_available=True,
            ),
            _native_job_payload(
                id=failed_id,
                action="check_updates",
                state="failed",
                host_name="Node 01",
                started_at="2026-01-15T17:52:00Z",
                finished_at="2026-01-15T17:53:00Z",
                exit_code=0,
                error_code="invalid_ansible_output",
                short_error="Ansible returned an invalid structured result",
                duration=60,
                log_available=True,
            ),
        ],
    )
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/custom-tasks", json=[]
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="backend.example.invalid",
        version=2,
        minor_version=1,
        unique_id=f"native|{NATIVE_URL}",
        data={
            CONF_BACKEND_TYPE: BACKEND_NATIVE,
            CONF_BACKEND_URL: NATIVE_URL,
            "api_token": API_TOKEN,
            CONF_POLL_INTERVAL: 300,
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    connectivity = hass.states.get("binary_sensor.homelab_updates_backend_connectivity")
    assert connectivity is not None
    assert connectivity.state == "on"
    assert connectivity.attributes["device_class"] == "connectivity"
    latest = hass.states.get("sensor.homelab_updates_last_job")
    historical = hass.states.get("sensor.homelab_updates_last_failed_job")
    host_latest = hass.states.get("sensor.node_01_last_job")
    host_historical = hass.states.get("sensor.node_01_last_failed_job")
    assert latest is not None
    assert historical is not None
    assert host_latest is not None
    assert host_historical is not None
    assert latest.state == host_latest.state == "success"
    assert latest.attributes["type"] == "check_updates"
    assert historical.state == host_historical.state == "failed"
    assert historical.attributes["job_id"] == failed_id
    assert historical.attributes["error_code"] == "invalid_ansible_output"
    assert historical.attributes["finished_at"] == "2026-01-15T17:53:00+00:00"
    last_type = hass.states.get("sensor.homelab_updates_last_job_type")
    assert last_type is not None
    assert last_type.state == "check_updates"
    assert "output" not in latest.attributes
    assert "output" not in historical.attributes
    assert API_TOKEN not in historical.attributes["job_url"]
