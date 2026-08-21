"""Native update entities for managed host packages."""

from typing import Any

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomelabUpdatesConfigEntry
from .application import TaskManager
from .coordinator import HomelabUpdatesCoordinator
from .domain import Command
from .entity import (
    HomelabUpdatesEntity,
    async_setup_dynamic_host_entities,
    async_start_command,
    safe_extra_kwargs,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomelabUpdatesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up native update entities."""
    runtime = entry.runtime_data
    async_setup_dynamic_host_entities(
        entry,
        async_add_entities,
        lambda host_id: HomelabSystemUpdateEntity(
            runtime.coordinator,
            runtime.task_manager,
            host_id,
        ),
    )


class HomelabSystemUpdateEntity(HomelabUpdatesEntity, UpdateEntity):
    """Represent package update availability for one host."""

    _attr_translation_key = "system_updates"
    _attr_title = "System packages"
    _attr_supported_features = UpdateEntityFeature.INSTALL

    def __init__(
        self,
        coordinator: HomelabUpdatesCoordinator,
        task_manager: TaskManager,
        host_id: str,
    ) -> None:
        """Initialize a native update entity."""
        super().__init__(coordinator, host_id, "system_update")
        self._task_manager = task_manager

    async def async_added_to_hass(self) -> None:
        """Listen for task progress in addition to coordinator status."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._task_manager.async_add_listener(self._async_task_updated)
        )

    @callback
    def _async_task_updated(self) -> None:
        """Write in-progress changes from the task manager."""
        self.async_write_ha_state()

    @property
    def installed_version(self) -> str:
        """Return the controlled package-count baseline."""
        return "0"

    @property
    def latest_version(self) -> str:
        """Return the number of currently available packages."""
        return str(self.host_status.updates)

    @property
    def release_summary(self) -> str:
        """Return a compact update and security package summary."""
        status = self.host_status
        return f"{status.updates} updates, {status.security_updates} security updates"

    @property
    def in_progress(self) -> bool:
        """Return whether this host update task is being tracked."""
        return self._task_manager.is_running(Command.UPDATE_HOST, self._host_id)

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Use package availability instead of lexical version comparison."""
        return self.host_status.updates > 0

    async def async_install(
        self,
        version: str | None,
        backup: bool,
        **kwargs: Any,
    ) -> None:
        """Start a host-limited update task."""
        safe_extra_kwargs(kwargs)
        await async_start_command(
            self._task_manager,
            Command.UPDATE_HOST,
            self._host_id,
        )
        self.async_write_ha_state()
