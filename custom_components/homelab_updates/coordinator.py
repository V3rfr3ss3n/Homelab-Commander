"""Central host status coordinator."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .application import AutomationBackend, HostProvider
from .const import DOMAIN
from .domain import BackendTask, CustomTaskDefinition, HostStatus
from .exceptions import HomelabUpdatesError

_LOGGER = logging.getLogger(__name__)


class HomelabUpdatesCoordinator(DataUpdateCoordinator[dict[str, HostStatus]]):
    """Load all host statuses with one request per interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        status_provider: HostProvider,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self._status_provider = status_provider

    async def _async_update_data(self) -> dict[str, HostStatus]:
        """Fetch and copy one complete status snapshot."""
        try:
            return dict(await self._status_provider.async_get_hosts())
        except HomelabUpdatesError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="status_update_failed",
            ) from err


class BackendJobsCoordinator(DataUpdateCoordinator[tuple[BackendTask, ...]]):
    """Poll provider-neutral job history for backend health and progress."""

    def __init__(
        self,
        hass: HomeAssistant,
        backend: AutomationBackend,
        update_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_jobs",
            update_interval=update_interval,
        )
        self._backend = backend

    async def _async_update_data(self) -> tuple[BackendTask, ...]:
        try:
            return tuple(await self._backend.async_get_tasks())
        except HomelabUpdatesError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="status_update_failed",
            ) from err


class CustomTasksCoordinator(DataUpdateCoordinator[dict[str, CustomTaskDefinition]]):
    """Discover backend-managed custom task definitions."""

    def __init__(
        self,
        hass: HomeAssistant,
        backend: AutomationBackend,
        update_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_custom_tasks",
            update_interval=update_interval,
        )
        self._backend = backend

    async def _async_update_data(self) -> dict[str, CustomTaskDefinition]:
        try:
            return {
                task.task_id: task
                for task in await self._backend.async_get_custom_tasks()
            }
        except HomelabUpdatesError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="status_update_failed",
            ) from err
