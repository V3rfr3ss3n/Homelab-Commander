"""Authenticated Home Assistant panel boundary tests."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

from aiohasupervisor.models.addons import AddonState
from homeassistant.components import frontend
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.homelab_updates.const import (
    BACKEND_NATIVE,
    CONF_BACKEND_TYPE,
    CONF_BACKEND_URL,
    CONF_POLL_INTERVAL,
    CONF_VERIFY_SSL,
    DOMAIN,
)
from custom_components.homelab_updates.domain import BackendTask, Command, TaskPhase
from custom_components.homelab_updates.panel import PANEL_URL_PATH
from custom_components.homelab_updates.supervisor import DiscoveredNativeBackend

from .conftest import API_TOKEN
from .test_api import (
    HOST_ID,
    JOB_ID,
    NATIVE_URL,
    _native_host_payload,
    _native_job_payload,
)

PANEL_SOURCE = (
    Path(__file__).parents[1] / "custom_components/homelab_updates/frontend/panel.js"
)


async def _setup_native_entry(
    hass: HomeAssistant,
    aioclient_mock: object,
    *,
    jobs: list[dict[str, object]] | None = None,
    backend_url: str = NATIVE_URL,
) -> MockConfigEntry:
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{backend_url}/api/v1/hosts", json=[_native_host_payload()]
    )
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{backend_url}/api/v1/jobs", json=jobs or []
    )
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{backend_url}/api/v1/custom-tasks", json=[]
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=backend_url.removeprefix("https://"),
        version=2,
        minor_version=1,
        unique_id=f"native|{backend_url}",
        data={
            CONF_BACKEND_TYPE: BACKEND_NATIVE,
            CONF_BACKEND_URL: backend_url,
            CONF_API_TOKEN: API_TOKEN,
            CONF_POLL_INTERVAL: 300,
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_panel_moves_to_next_loaded_native_entry_on_unload(
    hass: HomeAssistant,
    aioclient_mock: object,
) -> None:
    """The singleton sidebar panel has a deterministic multi-entry lifecycle."""
    first = await _setup_native_entry(hass, aioclient_mock)
    second_url = "https://backend-02.example.invalid"
    second = await _setup_native_entry(
        hass,
        aioclient_mock,
        backend_url=second_url,
    )
    panel = hass.data[frontend.DATA_PANELS][PANEL_URL_PATH]
    assert panel.config["entry_id"] == first.entry_id
    assert first.runtime_data.panel_registered is True
    assert second.runtime_data.panel_registered is False

    assert await hass.config_entries.async_unload(first.entry_id)
    await hass.async_block_till_done()

    replacement = hass.data[frontend.DATA_PANELS][PANEL_URL_PATH]
    assert replacement.config["entry_id"] == second.entry_id
    assert replacement.config["management_url"] == second_url
    assert second.runtime_data.panel_registered is True


async def test_local_app_management_link_uses_home_assistant_app_route(
    hass: HomeAssistant,
    aioclient_mock: object,
) -> None:
    """The panel opens local App Ingress instead of browser-invisible DNS."""
    slug = "synthetic_repository_homelab_updates"
    backend_url = "http://synthetic-repository-homelab-updates:8099"
    discovered = DiscoveredNativeBackend(
        name="Homelab Commander Backend",
        slug=slug,
        version="0.3.0-dev.0",
        state=AddonState.STARTED,
        url=backend_url,
    )

    with patch(
        "custom_components.homelab_updates.panel.async_discover_native_backend",
        AsyncMock(return_value=discovered),
    ):
        await _setup_native_entry(
            hass,
            aioclient_mock,
            backend_url=backend_url,
        )

    panel = hass.data[frontend.DATA_PANELS][PANEL_URL_PATH]
    assert panel.config["management_url"] == f"/app/{slug}"


async def test_admin_panel_supports_an_empty_job_history(
    hass: HomeAssistant,
    aioclient_mock: object,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A healthy backend without jobs publishes explicit empty latest states."""
    entry = await _setup_native_entry(hass, aioclient_mock)
    client = await hass_ws_client()

    await client.send_json_auto_id({
        "type": f"{DOMAIN}/subscribe_panel",
        "entry_id": entry.entry_id,
    })
    assert (await client.receive_json())["success"] is True
    snapshot = (await client.receive_json())["event"]

    assert snapshot["backend_online"] is True
    assert snapshot["jobs"] == []
    assert snapshot["last_job"] is None
    assert snapshot["last_failed_job"] is None


async def test_admin_panel_streams_metadata_and_fetches_log_explicitly(
    hass: HomeAssistant,
    aioclient_mock: object,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """The panel streams compact state while logs remain an explicit request."""
    failed_id = "00000000-0000-4000-8000-000000000003"
    entry = await _setup_native_entry(
        hass,
        aioclient_mock,
        jobs=[
            _native_job_payload(
                action="check_updates",
                state="success",
                host_name="Node 01",
                finished_at="2026-01-15T12:03:00Z",
                exit_code=0,
                log_available=True,
            ),
            _native_job_payload(
                id=failed_id,
                action="check_updates",
                state="failed",
                host_name="Node 01",
                finished_at="2026-01-15T11:03:00Z",
                exit_code=2,
                error_code="synthetic_failure",
                short_error="Synthetic failure",
                log_available=True,
            ),
        ],
    )
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/jobs/{JOB_ID}/log",
        json={
            "job_id": JOB_ID,
            "output": "Synthetic redacted output",
            "truncated": False,
        },
    )
    entry.runtime_data.task_manager.async_start = AsyncMock(  # type: ignore[method-assign]
        return_value=BackendTask(JOB_ID, TaskPhase.WAITING, "queued")
    )
    client = await hass_ws_client()

    await client.send_json_auto_id({
        "type": f"{DOMAIN}/subscribe_panel",
        "entry_id": entry.entry_id,
    })
    subscribed = await client.receive_json()
    event = await client.receive_json()
    assert subscribed["success"] is True
    assert event["type"] == "event"
    snapshot = event["event"]
    assert snapshot["backend_online"] is True
    assert snapshot["last_job"]["state"] == "success"
    assert snapshot["last_failed_job"]["error_code"] == "synthetic_failure"
    assert snapshot["hosts"][0]["host_id"] == HOST_ID
    assert "output" not in str(snapshot)
    assert API_TOKEN not in str(snapshot)

    await client.send_json_auto_id({
        "type": f"{DOMAIN}/job_log",
        "entry_id": entry.entry_id,
        "job_id": JOB_ID,
    })
    log_response = await client.receive_json()
    assert log_response["success"] is True
    assert log_response["result"] == {
        "job_id": JOB_ID,
        "output": "Synthetic redacted output",
        "truncated": False,
    }

    await client.send_json_auto_id({
        "type": f"{DOMAIN}/check_hosts",
        "entry_id": entry.entry_id,
    })
    check_response = await client.receive_json()
    assert check_response["success"] is True
    assert check_response["result"] == {"job_id": JOB_ID}
    entry.runtime_data.task_manager.async_start.assert_awaited_once_with(
        Command.CHECK_ALL
    )


async def test_panel_commands_reject_non_admin_users(
    hass: HomeAssistant,
    aioclient_mock: object,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Read-only users cannot subscribe, start checks, or retrieve job output."""
    entry = await _setup_native_entry(hass, aioclient_mock)
    client = await hass_ws_client(access_token=hass_read_only_access_token)

    for command in ("subscribe_panel", "check_hosts", "job_log"):
        message = {
            "type": f"{DOMAIN}/{command}",
            "entry_id": entry.entry_id,
        }
        if command == "job_log":
            message["job_id"] = JOB_ID
        await client.send_json_auto_id(message)
        response = await client.receive_json()
        assert response["success"] is False
        assert response["error"]["code"] == "unauthorized"


def test_panel_asset_avoids_browser_token_storage_and_unsafe_html() -> None:
    """The shipped panel stays on HA auth and renders backend text safely."""
    source = PANEL_SOURCE.read_text()

    assert PANEL_URL_PATH in source
    assert "homelab_updates/subscribe_panel" in source
    assert "homelab_updates/job_log" in source
    assert "Hosts prüfen" in source
    assert "Backend verwalten" in source
    for forbidden in (
        "localStorage",
        "sessionStorage",
        "document.cookie",
        "Authorization",
        "innerHTML",
    ):
        assert forbidden not in source
