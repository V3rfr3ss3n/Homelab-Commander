"""Repair flow for explicitly confirmed host reboots."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .domain import Command
from .entity import async_start_command

if TYPE_CHECKING:
    from . import HomelabUpdatesConfigEntry


class RebootRequiredRepairFlow(RepairsFlow):
    """Ask for confirmation before starting a required host reboot."""

    def __init__(self, entry_id: str, host_id: str) -> None:
        """Initialize the repair flow."""
        self._entry_id = entry_id
        self._host_id = host_id

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> RepairsFlowResult:
        """Open the confirmation step."""
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> RepairsFlowResult:
        """Validate current status and start the reboot after confirmation."""
        raw_entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if (
            raw_entry is None
            or raw_entry.domain != DOMAIN
            or raw_entry.state is not ConfigEntryState.LOADED
        ):
            return self.async_abort(reason="entry_unavailable")

        entry = cast("HomelabUpdatesConfigEntry", raw_entry)
        status = entry.runtime_data.coordinator.data.get(self._host_id)
        if status is None or not status.reboot_required:
            return self.async_abort(reason="no_longer_required")

        placeholders = {"host": status.display_name}
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                description_placeholders=placeholders,
            )

        try:
            await async_start_command(
                entry.runtime_data.task_manager,
                Command.REBOOT_HOST,
                self._host_id,
            )
        except HomeAssistantError:
            return self.async_show_form(
                step_id="confirm",
                errors={"base": "cannot_reboot"},
                description_placeholders=placeholders,
            )

        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a reboot confirmation flow from validated issue data."""
    if data is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_repair_issue",
        )

    entry_id = data.get("entry_id")
    host_id = data.get("host_id")
    if not isinstance(entry_id, str) or not entry_id:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_repair_issue",
        )
    if not isinstance(host_id, str) or not host_id:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_repair_issue",
        )

    return RebootRequiredRepairFlow(entry_id, host_id)
