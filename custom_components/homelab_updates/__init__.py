"""Home Assistant lifecycle for Homelab Updates."""

from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .adapters import SemaphoreClient, StatusClient
from .application import TaskManager
from .const import (
    CONF_CHECK_TEMPLATE_ID,
    CONF_EXPORT_TEMPLATE_ID,
    CONF_POLL_INTERVAL,
    CONF_PROJECT_ID,
    CONF_REBOOT_TEMPLATE_ID,
    CONF_SEMAPHORE_URL,
    CONF_STATUS_URL,
    CONF_UPDATE_TEMPLATE_ID,
    CONF_VERIFY_SSL,
    PLATFORMS,
)
from .coordinator import HomelabUpdatesCoordinator
from .domain import Command
from .reboot import async_remove_reboot_issues, async_sync_reboot_issues


@dataclass(slots=True)
class HomelabUpdatesRuntimeData:
    """Typed non-persistent objects owned by one config entry."""

    status_client: StatusClient
    semaphore_client: SemaphoreClient
    coordinator: HomelabUpdatesCoordinator
    task_manager: TaskManager
    reboot_issue_ids: set[str]


type HomelabUpdatesConfigEntry = ConfigEntry[HomelabUpdatesRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant, entry: HomelabUpdatesConfigEntry
) -> bool:
    """Set up Homelab Updates from a config entry."""
    session = async_get_clientsession(hass)
    verify_ssl = bool(entry.data[CONF_VERIFY_SSL])
    status_client = StatusClient(
        session,
        str(entry.data[CONF_STATUS_URL]),
        verify_ssl=verify_ssl,
    )
    semaphore_client = SemaphoreClient(
        session,
        str(entry.data[CONF_SEMAPHORE_URL]),
        str(entry.data[CONF_API_TOKEN]),
        int(entry.data[CONF_PROJECT_ID]),
        {
            Command.CHECK_ALL: int(entry.data[CONF_CHECK_TEMPLATE_ID]),
            Command.UPDATE_HOST: int(entry.data[CONF_UPDATE_TEMPLATE_ID]),
            Command.REBOOT_HOST: int(entry.data[CONF_REBOOT_TEMPLATE_ID]),
            Command.REFRESH_STATUS: int(entry.data[CONF_EXPORT_TEMPLATE_ID]),
        },
        verify_ssl=verify_ssl,
    )
    coordinator = HomelabUpdatesCoordinator(
        hass,
        status_client,
        timedelta(seconds=int(entry.data[CONF_POLL_INTERVAL])),
    )
    await coordinator.async_config_entry_first_refresh()

    def _start_reauth() -> None:
        entry.async_start_reauth(hass)

    task_manager = TaskManager(
        hass,
        semaphore_client,
        coordinator.async_request_refresh,
        _start_reauth,
    )
    entry.runtime_data = HomelabUpdatesRuntimeData(
        status_client=status_client,
        semaphore_client=semaphore_client,
        coordinator=coordinator,
        task_manager=task_manager,
        reboot_issue_ids=set(),
    )
    async_sync_reboot_issues(hass, entry)
    entry.async_on_unload(
        coordinator.async_add_listener(lambda: async_sync_reboot_issues(hass, entry))
    )
    entry.async_on_unload(lambda: async_remove_reboot_issues(hass, entry))
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HomelabUpdatesConfigEntry
) -> bool:
    """Unload platforms and cancel all background work."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.task_manager.async_cancel()
    return True


async def _async_reload_entry(
    hass: HomeAssistant, entry: HomelabUpdatesConfigEntry
) -> None:
    """Reload an entry after reconfiguration."""
    await hass.config_entries.async_reload(entry.entry_id)
