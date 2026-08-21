"""Shared synthetic fixtures for Homelab Updates tests."""

from datetime import UTC, datetime
from typing import Any

import pytest
from aiohttp import ClientSession
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homelab_updates.const import (
    CONF_CHECK_TEMPLATE_ID,
    CONF_EXPORT_TEMPLATE_ID,
    CONF_POLL_INTERVAL,
    CONF_PROJECT_ID,
    CONF_REBOOT_TEMPLATE_ID,
    CONF_SEMAPHORE_URL,
    CONF_STATUS_URL,
    CONF_UPDATE_TEMPLATE_ID,
    CONF_VERIFY_SSL,
    DEFAULT_CHECK_TEMPLATE_ID,
    DEFAULT_EXPORT_TEMPLATE_ID,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_REBOOT_TEMPLATE_ID,
    DEFAULT_UPDATE_TEMPLATE_ID,
    DOMAIN,
)
from custom_components.homelab_updates.domain import HostStatus

SEMAPHORE_URL = "https://semaphore.example.invalid"
STATUS_URL = "https://status.example.invalid/servers.json"
API_TOKEN = "synthetic-test-token"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: Any,
) -> None:
    """Enable loading the custom component in each HA test."""


@pytest.fixture
async def aiohttp_client_session(hass: HomeAssistant) -> ClientSession:
    """Return Home Assistant's shared test HTTP session."""
    return async_get_clientsession(hass)


@pytest.fixture
def config_data() -> dict[str, str | int | bool]:
    """Return complete synthetic config entry data."""
    return {
        CONF_SEMAPHORE_URL: SEMAPHORE_URL,
        CONF_API_TOKEN: API_TOKEN,
        CONF_PROJECT_ID: 1,
        CONF_STATUS_URL: STATUS_URL,
        CONF_CHECK_TEMPLATE_ID: DEFAULT_CHECK_TEMPLATE_ID,
        CONF_UPDATE_TEMPLATE_ID: DEFAULT_UPDATE_TEMPLATE_ID,
        CONF_REBOOT_TEMPLATE_ID: DEFAULT_REBOOT_TEMPLATE_ID,
        CONF_EXPORT_TEMPLATE_ID: DEFAULT_EXPORT_TEMPLATE_ID,
        CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
        CONF_VERIFY_SSL: True,
    }


@pytest.fixture
def mock_entry(config_data: dict[str, str | int | bool]) -> MockConfigEntry:
    """Return a synthetic config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="semaphore.example.invalid",
        data=config_data,
        unique_id=f"{SEMAPHORE_URL}|1",
    )


@pytest.fixture
def host_status() -> HostStatus:
    """Return a normalized synthetic host."""
    return HostStatus(
        host_id="node-01",
        hostname="example-node",
        distribution="Example Linux",
        distribution_version="1.0",
        kernel="1.0.0-generic",
        updates=5,
        security_updates=2,
        reboot_required=False,
        status="critical",
        checked_at=datetime(2026, 1, 15, 12, tzinfo=UTC),
    )
