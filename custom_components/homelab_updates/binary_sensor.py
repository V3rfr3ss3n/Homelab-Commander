"""Binary sensor platform for host reboot requirements."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomelabUpdatesConfigEntry
from .coordinator import HomelabUpdatesCoordinator
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
