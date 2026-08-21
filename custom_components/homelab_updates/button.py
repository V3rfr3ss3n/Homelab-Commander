"""Explicit maintenance action buttons."""

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomelabUpdatesConfigEntry
from .application import TaskManager
from .const import DOMAIN, NAME
from .coordinator import CustomTasksCoordinator, HomelabUpdatesCoordinator
from .domain import Command
from .entity import (
    HomelabUpdatesEntity,
    async_setup_dynamic_host_entities,
    async_start_command,
    async_start_custom_task,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomelabUpdatesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up global and dynamically discovered host buttons."""
    runtime = entry.runtime_data
    async_add_entities([
        HomelabGlobalButton(
            entry.entry_id,
            runtime.task_manager,
            Command.CHECK_ALL,
            "check_all",
            "mdi:update",
        ),
        HomelabGlobalButton(
            entry.entry_id,
            runtime.task_manager,
            Command.REFRESH_STATUS,
            "refresh_status",
            "mdi:database-refresh",
        ),
    ])
    async_setup_dynamic_host_entities(
        entry,
        async_add_entities,
        lambda host_id: HomelabRebootButton(
            runtime.coordinator,
            runtime.task_manager,
            host_id,
        ),
    )
    if runtime.custom_tasks_coordinator is not None:
        custom_tasks = runtime.custom_tasks_coordinator
        known_pairs: set[tuple[str, str]] = set()

        @callback
        def _async_add_custom_tasks() -> None:
            pairs = {
                (host_id, task_id)
                for host_id in runtime.coordinator.data
                for task_id in custom_tasks.data
            }
            new_pairs = pairs - known_pairs
            if not new_pairs:
                return
            known_pairs.update(new_pairs)
            async_add_entities([
                HomelabCustomTaskButton(
                    runtime.coordinator,
                    custom_tasks,
                    runtime.task_manager,
                    host_id,
                    task_id,
                )
                for host_id, task_id in sorted(new_pairs)
            ])

        _async_add_custom_tasks()
        entry.async_on_unload(
            runtime.coordinator.async_add_listener(_async_add_custom_tasks)
        )
        entry.async_on_unload(custom_tasks.async_add_listener(_async_add_custom_tasks))


class HomelabGlobalButton(ButtonEntity):
    """Run one global command on the configured backend."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry_id: str,
        task_manager: TaskManager,
        command: Command,
        translation_key: str,
        icon: str,
    ) -> None:
        """Initialize a global action button."""
        self._entry_id = entry_id
        self._task_manager = task_manager
        self._command = command
        self._attr_translation_key = translation_key
        self._attr_icon = icon
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{command.value}"

    async def async_added_to_hass(self) -> None:
        """Listen for command lifecycle changes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._task_manager.async_add_listener(self._async_task_updated)
        )

    @callback
    def _async_task_updated(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Prevent accidental duplicate global commands."""
        return not self._task_manager.is_running(self._command)

    @property
    def device_info(self) -> DeviceInfo:
        """Attach global commands to one integration hub device."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"hub_{self._entry_id}")},
            name=NAME,
            manufacturer=NAME,
            model="Automation hub",
        )

    async def async_press(self) -> None:
        """Start the configured global command."""
        await async_start_command(self._task_manager, self._command)
        self.async_write_ha_state()


class HomelabRebootButton(HomelabUpdatesEntity, ButtonEntity):
    """Explicitly request a reboot for one stable host ID."""

    _attr_translation_key = "reboot"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:restart-alert"

    def __init__(
        self,
        coordinator: HomelabUpdatesCoordinator,
        task_manager: TaskManager,
        host_id: str,
    ) -> None:
        """Initialize the host reboot button."""
        super().__init__(coordinator, host_id, "reboot")
        self._task_manager = task_manager

    async def async_added_to_hass(self) -> None:
        """Listen for command lifecycle changes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._task_manager.async_add_listener(self._async_task_updated)
        )

    @callback
    def _async_task_updated(self) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Only offer reboot when current status explicitly requires one."""
        return (
            super().available
            and self.host_status.reboot_required
            and not self._task_manager.is_running(Command.UPDATE_HOST, self._host_id)
            and not self._task_manager.is_running(Command.REBOOT_HOST, self._host_id)
        )

    async def async_press(self) -> None:
        """Start a host-limited reboot task."""
        await async_start_command(
            self._task_manager,
            Command.REBOOT_HOST,
            self._host_id,
        )
        self.async_write_ha_state()


class HomelabCustomTaskButton(HomelabUpdatesEntity, ButtonEntity):
    """Run one dynamically discovered custom task for one host."""

    _attr_icon = "mdi:play-box-outline"

    def __init__(
        self,
        coordinator: HomelabUpdatesCoordinator,
        custom_tasks: CustomTasksCoordinator,
        task_manager: TaskManager,
        host_id: str,
        task_id: str,
    ) -> None:
        super().__init__(coordinator, host_id, f"custom_task_{task_id}")
        self._custom_tasks = custom_tasks
        self._task_manager = task_manager
        self._task_id = task_id

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._custom_tasks.async_add_listener(self.async_write_ha_state)
        )
        self.async_on_remove(
            self._task_manager.async_add_listener(self.async_write_ha_state)
        )

    @property
    def name(self) -> str:
        task = self._custom_tasks.data.get(self._task_id)
        return task.name if task is not None else self._task_id

    @property
    def available(self) -> bool:
        task = self._custom_tasks.data.get(self._task_id)
        return (
            super().available
            and task is not None
            and task.enabled
            and not self._task_manager.is_custom_running(self._task_id, self._host_id)
        )

    async def async_press(self) -> None:
        await async_start_custom_task(self._task_manager, self._task_id, self._host_id)
        self.async_write_ha_state()
