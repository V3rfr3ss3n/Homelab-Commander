"""Central host status coordinator."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .application import StatusProvider
from .const import DOMAIN
from .domain import HostStatus
from .exceptions import HomelabUpdatesError

_LOGGER = logging.getLogger(__name__)


class HomelabUpdatesCoordinator(DataUpdateCoordinator[dict[str, HostStatus]]):
    """Load all host statuses with one request per interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        status_provider: StatusProvider,
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
