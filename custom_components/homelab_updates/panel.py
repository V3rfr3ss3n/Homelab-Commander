"""Home Assistant sidebar panel and authenticated panel data boundary."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol
from homeassistant.components import frontend, panel_custom
from homeassistant.components.http.server import StaticPathConfig
from homeassistant.components.websocket_api import async_register_command
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.decorators import (
    async_response,
    require_admin,
    websocket_command,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    BACKEND_NATIVE,
    CONF_BACKEND_TYPE,
    CONF_BACKEND_URL,
    DOMAIN,
    NAME,
    VERSION,
)
from .domain import BackendTask, Command, HostStatus, TaskPhase

if TYPE_CHECKING:
    from . import HomelabUpdatesConfigEntry

PANEL_URL_PATH = "homelab-updates"
PANEL_MODULE_URL = f"/{DOMAIN}/frontend/panel.js?v={VERSION}"
_PANEL_MODULE_PATH = Path(__file__).with_name("frontend") / "panel.js"


async def async_setup_panel_support(hass: HomeAssistant) -> None:
    """Serve the panel module and register its authenticated WebSocket commands."""
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            f"/{DOMAIN}/frontend/panel.js",
            str(_PANEL_MODULE_PATH),
            cache_headers=False,
        )
    ])
    async_register_command(hass, websocket_subscribe_panel)
    async_register_command(hass, websocket_get_job_log)
    async_register_command(hass, websocket_check_hosts)


async def async_register_panel(
    hass: HomeAssistant, entry: HomelabUpdatesConfigEntry
) -> bool:
    """Register the first loaded native entry as the admin-only main panel."""
    if entry.data.get(
        CONF_BACKEND_TYPE
    ) != BACKEND_NATIVE or frontend.async_panel_exists(hass, PANEL_URL_PATH):
        return False
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name="homelab-updates-panel",
        sidebar_title=NAME,
        sidebar_icon="mdi:server-network",
        module_url=PANEL_MODULE_URL,
        config={
            "entry_id": entry.entry_id,
            "management_url": str(entry.data[CONF_BACKEND_URL]),
        },
        require_admin=True,
        config_panel_domain=DOMAIN,
        handle_safe_area=True,
    )
    return True


async def async_unregister_panel(
    hass: HomeAssistant, entry: HomelabUpdatesConfigEntry
) -> None:
    """Remove an owned panel and promote another loaded native entry if present."""
    if not entry.runtime_data.panel_registered:
        return
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    entry.runtime_data.panel_registered = False
    for candidate in hass.config_entries.async_entries(DOMAIN):
        if (
            candidate.entry_id == entry.entry_id
            or candidate.state is not ConfigEntryState.LOADED
            or candidate.data.get(CONF_BACKEND_TYPE) != BACKEND_NATIVE
        ):
            continue
        typed_candidate = cast("HomelabUpdatesConfigEntry", candidate)
        typed_candidate.runtime_data.panel_registered = await async_register_panel(
            hass, typed_candidate
        )
        return


def _native_entry(hass: HomeAssistant, entry_id: str) -> HomelabUpdatesConfigEntry:
    entry = hass.config_entries.async_get_entry(entry_id)
    if (
        entry is None
        or entry.domain != DOMAIN
        or entry.state is not ConfigEntryState.LOADED
        or entry.data.get(CONF_BACKEND_TYPE) != BACKEND_NATIVE
    ):
        raise HomeAssistantError("The native Homelab Updates entry is unavailable")
    return cast("HomelabUpdatesConfigEntry", entry)


@websocket_command({
    vol.Required("type"): f"{DOMAIN}/subscribe_panel",
    vol.Required("entry_id"): cv.string,
})
@require_admin
@callback
def websocket_subscribe_panel(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Stream compact coordinator snapshots to one authenticated admin panel."""
    entry = _native_entry(hass, str(msg["entry_id"]))
    message_id = int(msg["id"])

    @callback
    def send_snapshot() -> None:
        connection.send_event(message_id, _panel_snapshot(entry))

    unsubscribers = [
        entry.runtime_data.coordinator.async_add_listener(send_snapshot),
        entry.runtime_data.task_manager.async_add_listener(send_snapshot),
    ]
    if entry.runtime_data.jobs_coordinator is not None:
        unsubscribers.append(
            entry.runtime_data.jobs_coordinator.async_add_listener(send_snapshot)
        )

    @callback
    def unsubscribe() -> None:
        for remove_listener in unsubscribers:
            remove_listener()

    connection.subscriptions[message_id] = unsubscribe
    connection.send_result(message_id)
    send_snapshot()


@websocket_command({
    vol.Required("type"): f"{DOMAIN}/job_log",
    vol.Required("entry_id"): cv.string,
    vol.Required("job_id"): cv.string,
})
@require_admin
@async_response
async def websocket_get_job_log(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return one explicit bounded log through Home Assistant admin auth."""
    entry = _native_entry(hass, str(msg["entry_id"]))
    log = await entry.runtime_data.automation_backend.async_get_job_log(
        str(msg["job_id"])
    )
    connection.send_result(
        int(msg["id"]),
        {
            "job_id": log.job_id,
            "output": log.output,
            "truncated": log.truncated,
        },
    )


@websocket_command({
    vol.Required("type"): f"{DOMAIN}/check_hosts",
    vol.Required("entry_id"): cv.string,
})
@require_admin
@async_response
async def websocket_check_hosts(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Start the single native host-check action from the main panel."""
    entry = _native_entry(hass, str(msg["entry_id"]))
    task = await entry.runtime_data.task_manager.async_start(Command.CHECK_ALL)
    connection.send_result(int(msg["id"]), {"job_id": str(task.task_id)})


def _panel_snapshot(entry: HomelabUpdatesConfigEntry) -> dict[str, object]:
    """Build a compact JSON-safe panel view without job output or secrets."""
    jobs_coordinator = entry.runtime_data.jobs_coordinator
    jobs = jobs_coordinator.data if jobs_coordinator is not None else ()
    latest = next(iter(jobs), None)
    latest_failed = next(
        (task for task in jobs if task.phase is TaskPhase.FAILED), None
    )
    return {
        "backend_online": bool(
            jobs_coordinator is not None and jobs_coordinator.last_update_success
        ),
        "checking": entry.runtime_data.task_manager.is_running(Command.CHECK_ALL),
        "running_jobs": sum(task.phase is TaskPhase.RUNNING for task in jobs),
        "queued_jobs": sum(task.phase is TaskPhase.WAITING for task in jobs),
        "last_job": _panel_job(latest),
        "last_failed_job": _panel_job(latest_failed),
        "hosts": [
            _panel_host(host) for host in entry.runtime_data.coordinator.data.values()
        ],
        "jobs": [_panel_job(task) for task in jobs],
    }


def _panel_host(host: HostStatus) -> dict[str, object]:
    return {
        "host_id": host.host_id,
        "name": host.display_name,
        "distribution": host.distribution_display,
        "updates": host.updates,
        "security_updates": host.security_updates,
        "reboot_required": host.reboot_required,
        "status": host.status,
        "checked_at": _timestamp(host.checked_at),
    }


def _panel_job(task: BackendTask | None) -> dict[str, object] | None:
    if task is None:
        return None
    return {
        "job_id": str(task.task_id),
        "host_id": task.host_id,
        "host_name": task.host_name,
        "type": task.action,
        "state": task.raw_status,
        "created_at": _timestamp(task.created_at),
        "started_at": _timestamp(task.started_at),
        "finished_at": _timestamp(task.finished_at),
        "duration": task.duration,
        "exit_code": task.exit_code,
        "error_code": task.error_code,
        "short_error": task.short_error,
        "log_available": task.log_available,
    }


def _timestamp(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
