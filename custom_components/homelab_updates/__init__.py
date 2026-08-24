"""Home Assistant lifecycle for Homelab Commander."""

from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .adapters import HttpStatusProvider, NativeBackendClient, SemaphoreBackend
from .application import AutomationBackend, HostProvider, TaskManager
from .const import (
    BACKEND_NATIVE,
    BACKEND_SEMAPHORE,
    CONF_BACKEND_TYPE,
    CONF_BACKEND_URL,
    CONF_CHECK_TEMPLATE_ID,
    CONF_EXPORT_TEMPLATE_ID,
    CONF_POLL_INTERVAL,
    CONF_PROJECT_ID,
    CONF_REBOOT_TEMPLATE_ID,
    CONF_SEMAPHORE_URL,
    CONF_STATUS_URL,
    CONF_UPDATE_TEMPLATE_ID,
    CONF_VERIFY_SSL,
    DOMAIN,
    NAME,
    PLATFORMS,
)
from .coordinator import (
    BackendJobsCoordinator,
    CustomTasksCoordinator,
    HomelabUpdatesCoordinator,
)
from .domain import Command
from .panel import (
    async_register_panel,
    async_setup_panel_support,
    async_unregister_panel,
)
from .reboot import async_remove_reboot_issues, async_sync_reboot_issues

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass(slots=True)
class HomelabUpdatesRuntimeData:
    """Typed non-persistent objects owned by one config entry."""

    host_provider: HostProvider
    automation_backend: AutomationBackend
    coordinator: HomelabUpdatesCoordinator
    jobs_coordinator: BackendJobsCoordinator | None
    custom_tasks_coordinator: CustomTasksCoordinator | None
    task_manager: TaskManager
    reboot_issue_ids: set[str]
    panel_registered: bool

    @property
    def status_client(self) -> HostProvider:
        """Return the host provider under its pre-0.2 compatibility name."""
        return self.host_provider

    @property
    def semaphore_client(self) -> AutomationBackend:
        """Return the backend under its pre-0.2 compatibility name."""
        return self.automation_backend


type HomelabUpdatesConfigEntry = ConfigEntry[HomelabUpdatesRuntimeData]


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up shared frontend assets and authenticated panel commands once."""
    await async_setup_panel_support(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: HomelabUpdatesConfigEntry
) -> bool:
    """Set up Homelab Commander from a config entry."""
    session = async_get_clientsession(hass)
    verify_ssl = bool(entry.data[CONF_VERIFY_SSL])
    backend_type = str(entry.data.get(CONF_BACKEND_TYPE, BACKEND_SEMAPHORE))
    if backend_type == BACKEND_NATIVE:
        native_backend = NativeBackendClient(
            session,
            str(entry.data[CONF_BACKEND_URL]),
            str(entry.data[CONF_API_TOKEN]),
            verify_ssl=verify_ssl,
        )
        host_provider: HostProvider = native_backend
        automation_backend: AutomationBackend = native_backend
    else:
        host_provider = HttpStatusProvider(
            session,
            str(entry.data[CONF_STATUS_URL]),
            verify_ssl=verify_ssl,
        )
        automation_backend = SemaphoreBackend(
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
        host_provider,
        timedelta(seconds=int(entry.data[CONF_POLL_INTERVAL])),
    )
    await coordinator.async_config_entry_first_refresh()
    jobs_coordinator: BackendJobsCoordinator | None = None
    custom_tasks_coordinator: CustomTasksCoordinator | None = None
    if backend_type == BACKEND_NATIVE:
        jobs_coordinator = BackendJobsCoordinator(
            hass,
            automation_backend,
            timedelta(seconds=int(entry.data[CONF_POLL_INTERVAL])),
        )
        await jobs_coordinator.async_config_entry_first_refresh()
        custom_tasks_coordinator = CustomTasksCoordinator(
            hass,
            automation_backend,
            timedelta(seconds=int(entry.data[CONF_POLL_INTERVAL])),
        )
        await custom_tasks_coordinator.async_config_entry_first_refresh()

    def _start_reauth() -> None:
        entry.async_start_reauth(hass)

    async def _refresh_runtime() -> None:
        await coordinator.async_request_refresh()
        if jobs_coordinator is not None:
            await jobs_coordinator.async_request_refresh()
        if custom_tasks_coordinator is not None:
            await custom_tasks_coordinator.async_request_refresh()

    task_manager = TaskManager(
        hass,
        automation_backend,
        _refresh_runtime,
        _start_reauth,
    )
    entry.runtime_data = HomelabUpdatesRuntimeData(
        host_provider=host_provider,
        automation_backend=automation_backend,
        coordinator=coordinator,
        jobs_coordinator=jobs_coordinator,
        custom_tasks_coordinator=custom_tasks_coordinator,
        task_manager=task_manager,
        reboot_issue_ids=set(),
        panel_registered=False,
    )
    entry.runtime_data.panel_registered = await async_register_panel(hass, entry)
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
    await async_unregister_panel(hass, entry)
    return True


async def async_migrate_entry(
    hass: HomeAssistant, entry: HomelabUpdatesConfigEntry
) -> bool:
    """Migrate persisted data without changing its technical identity."""
    if entry.version > 3:
        return False
    if entry.version < 3:
        data = dict(entry.data)
        if entry.version < 2:
            data.setdefault(CONF_BACKEND_TYPE, BACKEND_SEMAPHORE)
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            title=(
                NAME if data.get(CONF_BACKEND_TYPE) == BACKEND_NATIVE else entry.title
            ),
            version=3,
            minor_version=1,
        )
    return True


async def _async_reload_entry(
    hass: HomeAssistant, entry: HomelabUpdatesConfigEntry
) -> None:
    """Reload an entry after reconfiguration."""
    await hass.config_entries.async_reload(entry.entry_id)
