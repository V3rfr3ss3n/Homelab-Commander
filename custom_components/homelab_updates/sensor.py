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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomelabUpdatesConfigEntry
from .const import DOMAIN, NAME
from .coordinator import BackendJobsCoordinator, HomelabUpdatesCoordinator
from .domain import BackendTask, HostStatus, TaskPhase
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

    def _entities(host_ids: set[str]) -> list[SensorEntity]:
        entities: list[SensorEntity] = [
            HomelabUpdatesSensor(coordinator, host_id, description)
            for host_id in sorted(host_ids)
            for description in SENSOR_DESCRIPTIONS
        ]
        if entry.runtime_data.jobs_coordinator is not None:
            entities.extend(
                HomelabLastHostJobSensor(
                    coordinator,
                    entry.runtime_data.jobs_coordinator,
                    host_id,
                )
                for host_id in sorted(host_ids)
            )
        return entities

    async_add_entities(_entities(known_hosts))

    @callback
    def _async_add_new_hosts() -> None:
        new_hosts = set(coordinator.data) - known_hosts
        if not new_hosts:
            return
        known_hosts.update(new_hosts)
        async_add_entities(_entities(new_hosts))

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_hosts))
    if entry.runtime_data.jobs_coordinator is not None:
        async_add_entities([
            HomelabGlobalJobSensor(
                entry.runtime_data.jobs_coordinator,
                entry.entry_id,
                "queued_jobs",
            ),
            HomelabGlobalJobSensor(
                entry.runtime_data.jobs_coordinator,
                entry.entry_id,
                "running_jobs",
            ),
            HomelabGlobalJobSensor(
                entry.runtime_data.jobs_coordinator,
                entry.entry_id,
                "last_job_error",
            ),
        ])


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


class HomelabLastHostJobSensor(HomelabUpdatesEntity, SensorEntity):
    """Expose the latest backend job phase for one host."""

    _attr_translation_key = "last_job"
    _attr_icon = "mdi:progress-clock"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: HomelabUpdatesCoordinator,
        jobs_coordinator: BackendJobsCoordinator,
        host_id: str,
    ) -> None:
        super().__init__(coordinator, host_id, "last_job")
        self._jobs_coordinator = jobs_coordinator

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._jobs_coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def native_value(self) -> str | None:
        task = self._latest_task
        return task.phase.value if task is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        task = self._latest_task
        if task is None:
            return None
        return {
            "action": task.action or "unknown",
            "job_id": str(task.task_id),
        }

    @property
    def _latest_task(self) -> BackendTask | None:
        return next(
            (
                task
                for task in self._jobs_coordinator.data
                if task.host_id == self._host_id
            ),
            None,
        )


class HomelabGlobalJobSensor(SensorEntity):
    """Expose one provider-neutral native backend queue summary."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: BackendJobsCoordinator,
        entry_id: str,
        key: str,
    ) -> None:
        self._coordinator = coordinator
        self._entry_id = entry_id
        self._key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{key}"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def available(self) -> bool:
        return self._coordinator.last_update_success

    @property
    def native_value(self) -> int | str | None:
        if self._key == "queued_jobs":
            return sum(
                task.phase is TaskPhase.WAITING for task in self._coordinator.data
            )
        if self._key == "running_jobs":
            return sum(
                task.phase is TaskPhase.RUNNING for task in self._coordinator.data
            )
        failed = next(
            (task for task in self._coordinator.data if task.phase is TaskPhase.FAILED),
            None,
        )
        return failed.error_code if failed is not None else None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"hub_{self._entry_id}")},
            name=NAME,
            manufacturer=NAME,
            model="Native operations backend",
        )
