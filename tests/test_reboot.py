"""Reboot issue and confirmation flow tests."""

from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from homeassistant import data_entry_flow
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homelab_updates.const import DOMAIN
from custom_components.homelab_updates.exceptions import CannotConnectError
from custom_components.homelab_updates.reboot import reboot_issue_id
from custom_components.homelab_updates.repairs import async_create_fix_flow

from .conftest import SEMAPHORE_URL
from .test_init import _setup_entry


async def _require_reboot(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> str:
    runtime = entry.runtime_data
    host = runtime.coordinator.data["node-01"]
    runtime.coordinator.async_set_updated_data({
        "node-01": replace(host, reboot_required=True)
    })
    await hass.async_block_till_done()
    return reboot_issue_id(entry.entry_id, "node-01")


async def test_reboot_required_creates_fixable_issue(
    hass: HomeAssistant,
    aioclient_mock: object,
    mock_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A reboot flag creates a privacy-safe, actionable repair issue."""
    await _setup_entry(hass, aioclient_mock, mock_entry)
    issue_id = await _require_reboot(hass, mock_entry)

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.is_fixable
    assert issue.translation_key == "reboot_required"
    assert "node-01" not in issue_id
    assert issue.data == {
        "entry_id": mock_entry.entry_id,
        "host_id": "node-01",
        "host_name": "example-node",
    }

    runtime = mock_entry.runtime_data
    host = runtime.coordinator.data["node-01"]
    runtime.coordinator.async_set_updated_data({
        "node-01": replace(host, reboot_required=False)
    })
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_reboot_repair_flow_requires_confirmation(
    hass: HomeAssistant,
    aioclient_mock: object,
    mock_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Submitting the repair confirmation starts one host-limited reboot."""
    await _setup_entry(hass, aioclient_mock, mock_entry)
    issue_id = await _require_reboot(hass, mock_entry)
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None

    flow = await async_create_fix_flow(hass, issue_id, issue.data)
    flow.hass = hass
    form = await flow.async_step_init()
    assert form["type"] is data_entry_flow.FlowResultType.FORM
    assert form["step_id"] == "confirm"

    task_url = f"{SEMAPHORE_URL}/api/project/1/tasks"
    aioclient_mock.post(task_url, json={"id": 501})  # type: ignore[attr-defined]
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{task_url}/501",
        json={"id": 501, "status": "success"},
    )
    mock_entry.runtime_data.task_manager._poll_interval = 0

    result = await flow.async_step_confirm({})
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    post = next(
        call
        for call in aioclient_mock.mock_calls
        if call[0] == "POST"  # type: ignore[attr-defined]
    )
    assert post[2] == {"template_id": 3, "limit": "node-01"}


async def test_reboot_repair_flow_aborts_when_no_longer_required(
    hass: HomeAssistant,
    aioclient_mock: object,
    mock_entry: MockConfigEntry,
) -> None:
    """A stale repair cannot restart a host that no longer requires it."""
    await _setup_entry(hass, aioclient_mock, mock_entry)
    flow = await async_create_fix_flow(
        hass,
        "reboot_required_synthetic",
        {
            "entry_id": mock_entry.entry_id,
            "host_id": "node-01",
            "host_name": "example-node",
        },
    )
    flow.hass = hass

    result = await flow.async_step_init()
    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "no_longer_required"


async def test_reboot_repair_flow_handles_unavailable_entry(
    hass: HomeAssistant,
) -> None:
    """A removed config entry cannot be used by a stale repair flow."""
    flow = await async_create_fix_flow(
        hass,
        "reboot_required_synthetic",
        {"entry_id": "removed-entry", "host_id": "node-01"},
    )
    flow.hass = hass

    result = await flow.async_step_init()
    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "entry_unavailable"


async def test_reboot_repair_flow_reports_start_failure(
    hass: HomeAssistant,
    aioclient_mock: object,
    mock_entry: MockConfigEntry,
) -> None:
    """A rejected command keeps the confirmation form open with an error."""
    await _setup_entry(hass, aioclient_mock, mock_entry)
    await _require_reboot(hass, mock_entry)
    mock_entry.runtime_data.task_manager.async_start = AsyncMock(
        side_effect=CannotConnectError()
    )
    flow = await async_create_fix_flow(
        hass,
        "reboot_required_synthetic",
        {"entry_id": mock_entry.entry_id, "host_id": "node-01"},
    )
    flow.hass = hass

    result = await flow.async_step_confirm({})
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_reboot"}


@pytest.mark.parametrize(
    "data",
    [None, {}, {"entry_id": "entry-without-host"}],
)
async def test_invalid_reboot_repair_data_is_rejected(
    hass: HomeAssistant,
    data: dict[str, str] | None,
) -> None:
    """Malformed issue data never reaches an automation backend."""
    with pytest.raises(HomeAssistantError):
        await async_create_fix_flow(hass, "invalid", data)
