"""Sensor platform for normalized host status."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomelabUpdatesConfigEntry
from .coordinator import HomelabUpdatesCoordinator
from .domain import HostStatus
from .entity import HomelabUpdatesEntity

type SensorValue = str | int | float | datetime | Decimal | None


@dataclass(frozen=True, kw_only=True)
class HomelabSensorEntityDescription(SensorEntityDescription):
    """Describe a typed extraction from HostStatus."""

    value_fn: Callable[[HostStatus], SensorValue]


SENSOR_DESCRIPTIONS = (
    HomelabSensorEntityDescription(
        key="available_updates",
        translation_key="available_updates",
        icon="mdi:package-up",
        native_unit_of_measurement="updates",
        value_fn=lambda status: status.updates,
    ),
    HomelabSensorEntityDescription(
        key="security_updates",
        translation_key="security_updates",
        icon="mdi:shield-alert",
        native_unit_of_measurement="updates",
        value_fn=lambda status: status.security_updates,
    ),
    HomelabSensorEntityDescription(
        key="kernel",
        translation_key="kernel",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.kernel,
    ),
    HomelabSensorEntityDescription(
        key="distribution",
        translation_key="distribution",
        icon="mdi:linux",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.distribution_display,
    ),
    HomelabSensorEntityDescription(
        key="last_check",
        translation_key="last_check",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.checked_at,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomelabUpdatesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors and dynamically discover later hosts."""
    coordinator = entry.runtime_data.coordinator
    known_hosts = set(coordinator.data)

    def _entities(host_ids: set[str]) -> list[HomelabUpdatesSensor]:
        return [
            HomelabUpdatesSensor(coordinator, host_id, description)
            for host_id in sorted(host_ids)
            for description in SENSOR_DESCRIPTIONS
        ]

    async_add_entities(_entities(known_hosts))

    @callback
    def _async_add_new_hosts() -> None:
        new_hosts = set(coordinator.data) - known_hosts
        if not new_hosts:
            return
        known_hosts.update(new_hosts)
        async_add_entities(_entities(new_hosts))

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_hosts))


class HomelabUpdatesSensor(HomelabUpdatesEntity, SensorEntity):
    """One host status sensor."""

    entity_description: HomelabSensorEntityDescription

    def __init__(
        self,
        coordinator: HomelabUpdatesCoordinator,
        host_id: str,
        description: HomelabSensorEntityDescription,
    ) -> None:
        """Initialize a described sensor."""
        super().__init__(coordinator, host_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> SensorValue:
        """Return a pre-normalized value without I/O."""
        return self.entity_description.value_fn(self.host_status)
