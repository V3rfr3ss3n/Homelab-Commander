"""Shared Home Assistant entity primitives."""

from collections.abc import Callable
from typing import Any

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HomelabUpdatesConfigEntry
from .application import TaskManager
from .const import DOMAIN, NAME
from .coordinator import HomelabUpdatesCoordinator
from .domain import Command, HostStatus
from .exceptions import (
    AuthenticationError,
    HomelabUpdatesError,
    TaskAlreadyRunningError,
)

HostEntityFactory = Callable[[str], Entity]


class HomelabUpdatesEntity(CoordinatorEntity[HomelabUpdatesCoordinator]):
    """Base for entities backed by one host in the coordinator snapshot."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HomelabUpdatesCoordinator,
        host_id: str,
        entity_key: str,
    ) -> None:
        """Initialize one stable host entity."""
        super().__init__(coordinator)
        self._host_id = host_id
        self._attr_unique_id = f"{DOMAIN}_{host_id}_{entity_key}"

    @property
    def host_status(self) -> HostStatus:
        """Return the current host model for an available entity."""
        return self.coordinator.data[self._host_id]

    @property
    def available(self) -> bool:
        """Return availability for this specific host snapshot."""
        return super().available and self._host_id in self.coordinator.data

    @property
    def device_info(self) -> DeviceInfo:
        """Return stable device identity with mutable descriptive metadata."""
        status = self.coordinator.data.get(self._host_id)
        return DeviceInfo(
            identifiers={(DOMAIN, self._host_id)},
            name=status.display_name if status is not None else self._host_id,
            manufacturer=NAME,
            model=(status.distribution_display if status is not None else None),
            sw_version=(status.kernel if status is not None else None),
        )


def async_setup_dynamic_host_entities(
    entry: HomelabUpdatesConfigEntry,
    async_add_entities: AddEntitiesCallback,
    factory: HostEntityFactory,
) -> None:
    """Add current hosts and listen for hosts discovered after setup."""
    coordinator = entry.runtime_data.coordinator
    known_hosts = set(coordinator.data)
    async_add_entities([factory(host_id) for host_id in sorted(known_hosts)])

    @callback
    def _async_add_new_hosts() -> None:
        new_hosts = set(coordinator.data) - known_hosts
        if not new_hosts:
            return
        known_hosts.update(new_hosts)
        async_add_entities([factory(host_id) for host_id in sorted(new_hosts)])

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_hosts))


async def async_start_command(
    task_manager: TaskManager,
    command: Command,
    host_id: str | None = None,
) -> None:
    """Translate application errors into safe, localized HA action errors."""
    try:
        await task_manager.async_start(command, host_id)
    except AuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except TaskAlreadyRunningError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="task_already_running",
        ) from err
    except HomelabUpdatesError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="task_start_failed",
        ) from err


async def async_start_custom_task(
    task_manager: TaskManager, task_id: str, host_id: str
) -> None:
    """Start a provider-defined task with the standard safe error mapping."""
    try:
        await task_manager.async_start_custom(task_id, host_id)
    except AuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except TaskAlreadyRunningError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="task_already_running",
        ) from err
    except HomelabUpdatesError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="task_start_failed",
        ) from err


def safe_extra_kwargs(kwargs: dict[str, Any]) -> None:
    """Consume HA update kwargs without using or logging their contents."""
