"""Privacy-preserving diagnostics for Homelab Updates."""

from typing import Any

from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from yarl import URL

from . import HomelabUpdatesConfigEntry
from .const import (
    CONF_POLL_INTERVAL,
    CONF_SEMAPHORE_URL,
    CONF_STATUS_URL,
    CONF_VERIFY_SSL,
    VERSION,
)

_REDACTED = "**REDACTED**"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: HomelabUpdatesConfigEntry,
) -> dict[str, Any]:
    """Return an allowlisted diagnostic payload without host identities."""
    runtime = entry.runtime_data
    return {
        "integration_version": VERSION,
        "config": {
            CONF_SEMAPHORE_URL: _safe_url(str(entry.data[CONF_SEMAPHORE_URL])),
            CONF_STATUS_URL: _safe_url(str(entry.data[CONF_STATUS_URL])),
            CONF_API_TOKEN: _REDACTED,
            CONF_POLL_INTERVAL: int(entry.data[CONF_POLL_INTERVAL]),
            CONF_VERIFY_SSL: bool(entry.data[CONF_VERIFY_SSL]),
        },
        "runtime": {
            "coordinator_last_update_success": (
                runtime.coordinator.last_update_success
            ),
            "host_count": len(runtime.coordinator.data),
            "active_task_count": runtime.task_manager.active_task_count,
        },
    }


def _safe_url(value: str) -> str:
    """Remove credentials, query values, and fragments from a diagnostic URL."""
    url = URL(value)
    if url.user is not None:
        url = url.with_user(None)
    return str(url.with_query(None).with_fragment(None))
