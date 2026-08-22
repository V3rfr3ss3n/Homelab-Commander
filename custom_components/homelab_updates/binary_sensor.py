"""Binary sensor platform for host reboot requirements."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomelabUpdatesConfigEntry
from .const import DOMAIN, NAME
from .coordinator import BackendJobsCoordinator, HomelabUpdatesCoordinator
from .entity import HomelabUpdatesEntity, async_setup_dynamic_host_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomelabUpdatesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up reboot-required sensors."""
    coordinator = entry.runtime_data.coordinator
    async_setup_dynamic_host_entities(
        entry,
        async_add_entities,
        lambda host_id: HomelabRebootRequiredBinarySensor(coordinator, host_id),
    )
    if entry.runtime_data.jobs_coordinator is not None:
        async_add_entities([
            HomelabBackendHealthBinarySensor(
                entry.runtime_data.jobs_coordinator, entry.entry_id
            )
        ])


class HomelabRebootRequiredBinarySensor(HomelabUpdatesEntity, BinarySensorEntity):
    """Report whether a host requests a reboot."""

    _attr_translation_key = "reboot_required"
    _attr_icon = "mdi:restart-alert"

    def __init__(self, coordinator: HomelabUpdatesCoordinator, host_id: str) -> None:
        """Initialize the reboot sensor."""
        super().__init__(coordinator, host_id, "reboot_required")

    @property
    def is_on(self) -> bool:
        """Return the normalized reboot flag."""
        return self.host_status.reboot_required


class HomelabBackendHealthBinarySensor(
    BinarySensorEntity,
):
    """Report successful communication with the native job API."""

    _attr_has_entity_name = True
    _attr_translation_key = "backend_health"
    _attr_icon = "mdi:server-network"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: BackendJobsCoordinator, entry_id: str) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_backend_health"
        self._entry_id = entry_id

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def is_on(self) -> bool:
        return self._coordinator.last_update_success

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"hub_{self._entry_id}")},
            name=NAME,
            manufacturer=NAME,
            model="Native operations backend",
        )
