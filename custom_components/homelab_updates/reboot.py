"""Reboot-required repair issue lifecycle."""

from __future__ import annotations

from hashlib import sha256
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

if TYPE_CHECKING:
    from . import HomelabUpdatesConfigEntry


def reboot_issue_id(entry_id: str, host_id: str) -> str:
    """Return a stable issue ID without exposing the backend host identifier."""
    digest = sha256(f"{entry_id}\0{host_id}".encode()).hexdigest()[:16]
    return f"reboot_required_{digest}"


@callback
def async_sync_reboot_issues(
    hass: HomeAssistant,
    entry: HomelabUpdatesConfigEntry,
) -> None:
    """Create actionable issues for hosts that currently require a reboot."""
    runtime = entry.runtime_data
    current_issue_ids: set[str] = set()

    for status in runtime.coordinator.data.values():
        issue_id = reboot_issue_id(entry.entry_id, status.host_id)
        if not status.reboot_required:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
            continue

        current_issue_ids.add(issue_id)
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            data={
                "entry_id": entry.entry_id,
                "host_id": status.host_id,
                "host_name": status.display_name,
            },
            is_fixable=True,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="reboot_required",
            translation_placeholders={"host": status.display_name},
        )

    for stale_issue_id in runtime.reboot_issue_ids - current_issue_ids:
        ir.async_delete_issue(hass, DOMAIN, stale_issue_id)
    runtime.reboot_issue_ids = current_issue_ids


@callback
def async_remove_reboot_issues(
    hass: HomeAssistant,
    entry: HomelabUpdatesConfigEntry,
) -> None:
    """Remove non-persistent issues when the config entry unloads."""
    for issue_id in entry.runtime_data.reboot_issue_ids:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
    entry.runtime_data.reboot_issue_ids.clear()
