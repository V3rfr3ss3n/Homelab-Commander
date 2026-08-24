"""Config flow, duplicate, reauth, and reconfigure tests."""

from collections.abc import Mapping
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from aiohasupervisor.models.addons import AddonState
from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homelab_updates.config_flow import _normalize_data
from custom_components.homelab_updates.const import (
    BACKEND_NATIVE,
    BACKEND_SEMAPHORE,
    CONF_BACKEND_TYPE,
    CONF_BACKEND_URL,
    CONF_NATIVE_CONNECTION,
    CONF_POLL_INTERVAL,
    CONF_SEMAPHORE_URL,
    DOMAIN,
    NATIVE_CONNECTION_REMOTE,
)
from custom_components.homelab_updates.exceptions import (
    AuthenticationError,
    CannotConnectError,
    InvalidProjectError,
    InvalidStatusDataError,
)
from custom_components.homelab_updates.supervisor import DiscoveredNativeBackend


def _validation_patches(
    semaphore_error: Exception | None = None,
    status_error: Exception | None = None,
) -> tuple[patch, patch]:
    return (
        patch(
            (
                "custom_components.homelab_updates.config_flow."
                "SemaphoreClient.async_validate"
            ),
            AsyncMock(side_effect=semaphore_error),
        ),
        patch(
            "custom_components.homelab_updates.config_flow.StatusClient.async_validate",
            AsyncMock(side_effect=status_error),
        ),
    )


async def test_successful_config_flow(
    hass: HomeAssistant,
    config_data: Mapping[str, str | int | bool],
) -> None:
    """Valid input creates a normalized config entry."""
    semaphore_patch, status_patch = _validation_patches()
    with semaphore_patch, status_patch:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_BACKEND_TYPE: BACKEND_SEMAPHORE},
        )
        assert result["step_id"] == "semaphore"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=dict(config_data)
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_TOKEN] == config_data[CONF_API_TOKEN]
    assert result["title"] == "semaphore.example.invalid"


async def test_successful_native_config_flow(hass: HomeAssistant) -> None:
    """Native configuration only asks for its URL, token, TLS and interval."""
    native_data = {
        CONF_BACKEND_URL: "https://backend.example.invalid/",
        CONF_API_TOKEN: "synthetic-native-token",
        CONF_POLL_INTERVAL: 300,
        "verify_ssl": True,
    }
    with patch(
        (
            "custom_components.homelab_updates.config_flow."
            "NativeBackendClient.async_validate"
        ),
        AsyncMock(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_BACKEND_TYPE: BACKEND_NATIVE},
        )
        assert result["step_id"] == "native"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], native_data
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        **native_data,
        CONF_BACKEND_TYPE: BACKEND_NATIVE,
        CONF_BACKEND_URL: "https://backend.example.invalid",
    }
    assert result["title"] == "Homelab Commander"


def _schema_keys(result: Mapping[str, object]) -> set[str]:
    """Return field names from a Home Assistant flow schema."""
    schema = result["data_schema"]
    assert isinstance(schema, vol.Schema)
    return {str(marker.schema) for marker in schema.schema}


async def test_native_config_flow_uses_discovered_local_app(
    hass: HomeAssistant,
) -> None:
    """A running local App hides its implementation-only internal URL."""
    discovered = DiscoveredNativeBackend(
        name="Homelab Commander Backend",
        slug="synthetic_repository_homelab_updates",
        version="0.3.0-dev.0",
        state=AddonState.STARTED,
        url="http://synthetic-repository-homelab-updates:8099",
    )
    with (
        patch(
            (
                "custom_components.homelab_updates.config_flow."
                "async_discover_native_backend"
            ),
            AsyncMock(return_value=discovered),
        ),
        patch(
            (
                "custom_components.homelab_updates.config_flow."
                "NativeBackendClient.async_validate"
            ),
            AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_BACKEND_TYPE: BACKEND_NATIVE},
        )
        assert result["step_id"] == "native"
        assert CONF_BACKEND_URL not in _schema_keys(result)
        assert CONF_NATIVE_CONNECTION in _schema_keys(result)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NATIVE_CONNECTION: "local_app",
                CONF_API_TOKEN: "synthetic-native-token",
                CONF_POLL_INTERVAL: 300,
                "verify_ssl": True,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BACKEND_URL] == discovered.url
    assert CONF_NATIVE_CONNECTION not in result["data"]


async def test_native_config_flow_offers_remote_fallback_when_requested(
    hass: HomeAssistant,
) -> None:
    """A detected App never removes the remote and standalone option."""
    discovered = DiscoveredNativeBackend(
        name="Homelab Commander Backend",
        slug="synthetic_repository_homelab_updates",
        version="0.3.0-dev.0",
        state=AddonState.STARTED,
        url="http://synthetic-repository-homelab-updates:8099",
    )
    with patch(
        ("custom_components.homelab_updates.config_flow.async_discover_native_backend"),
        AsyncMock(return_value=discovered),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_BACKEND_TYPE: BACKEND_NATIVE},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NATIVE_CONNECTION: NATIVE_CONNECTION_REMOTE},
        )

    assert result["step_id"] == "native"
    assert CONF_BACKEND_URL in _schema_keys(result)


async def test_existing_remote_native_reconfigure_keeps_manual_url(
    hass: HomeAssistant,
) -> None:
    """Discovery never overwrites an existing remote backend configuration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Homelab Commander",
        data={
            CONF_BACKEND_TYPE: BACKEND_NATIVE,
            CONF_BACKEND_URL: "https://backend.example.invalid",
            CONF_API_TOKEN: "synthetic-native-token",
            CONF_POLL_INTERVAL: 300,
            "verify_ssl": True,
        },
        version=3,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    assert result["step_id"] == "reconfigure"
    assert CONF_BACKEND_URL in _schema_keys(result)
    assert entry.data[CONF_BACKEND_URL] == "https://backend.example.invalid"


@pytest.mark.parametrize(
    ("semaphore_error", "status_error", "expected"),
    [
        (AuthenticationError(), None, "invalid_auth"),
        (InvalidProjectError(), None, "invalid_project"),
        (CannotConnectError(), None, "cannot_connect"),
        (None, CannotConnectError(), "cannot_connect"),
        (None, InvalidStatusDataError(), "invalid_status_data"),
    ],
)
async def test_config_flow_errors(
    hass: HomeAssistant,
    config_data: Mapping[str, str | int | bool],
    semaphore_error: Exception | None,
    status_error: Exception | None,
    expected: str,
) -> None:
    """Expected service failures map to stable flow errors."""
    semaphore_patch, status_patch = _validation_patches(semaphore_error, status_error)
    with semaphore_patch, status_patch:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=dict(config_data),
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_config_flow_invalid_url(
    hass: HomeAssistant,
    config_data: Mapping[str, str | int | bool],
) -> None:
    """Malformed URLs fail before any network validation."""
    data = dict(config_data)
    data[CONF_SEMAPHORE_URL] = "file:///not-allowed"
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=data,
    )
    assert result["errors"] == {"base": "invalid_url"}


async def test_duplicate_entry_aborts(
    hass: HomeAssistant,
    config_data: Mapping[str, str | int | bool],
    mock_entry: MockConfigEntry,
) -> None:
    """The same normalized backend project cannot be configured twice."""
    mock_entry.add_to_hass(hass)
    semaphore_patch, status_patch = _validation_patches()
    with semaphore_patch, status_patch:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=dict(config_data),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauthentication(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
) -> None:
    """A replacement token is validated and stored through the UI."""
    mock_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_entry.entry_id,
        },
        data=dict(mock_entry.data),
    )
    assert result["step_id"] == "reauth_confirm"

    semaphore_patch, status_patch = _validation_patches()
    with semaphore_patch, status_patch:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "replacement-test-token"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_entry.data[CONF_API_TOKEN] == "replacement-test-token"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AuthenticationError(), "invalid_auth"),
        (CannotConnectError(), "cannot_connect"),
        (InvalidProjectError(), "unknown"),
    ],
)
async def test_reauthentication_errors(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    error: Exception,
    expected: str,
) -> None:
    """Reauth keeps the form open with a safe error category."""
    mock_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_entry.entry_id,
        },
        data=dict(mock_entry.data),
    )
    semaphore_patch, status_patch = _validation_patches(error)
    with semaphore_patch, status_patch:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "replacement-test-token"},
        )
    assert result["errors"] == {"base": expected}


async def test_reconfigure(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    config_data: Mapping[str, str | int | bool],
) -> None:
    """Endpoints, templates, and poll interval can be updated in-place."""
    mock_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_entry.entry_id,
        },
    )
    assert result["step_id"] == "reconfigure"

    changed = dict(config_data)
    changed.pop(CONF_API_TOKEN)
    changed[CONF_POLL_INTERVAL] = 600
    semaphore_patch, status_patch = _validation_patches()
    with semaphore_patch, status_patch:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            changed,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_entry.data[CONF_POLL_INTERVAL] == 600
    assert mock_entry.data[CONF_API_TOKEN] == "synthetic-test-token"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AuthenticationError(), "invalid_auth"),
        (InvalidProjectError(), "invalid_project"),
        (InvalidStatusDataError(), "invalid_status_data"),
        (CannotConnectError(), "cannot_connect"),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    config_data: Mapping[str, str | int | bool],
    error: Exception,
    expected: str,
) -> None:
    """Reconfigure preserves the existing entry after validation failures."""
    mock_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_entry.entry_id,
        },
    )
    changed = dict(config_data)
    changed.pop(CONF_API_TOKEN)
    semaphore_patch, status_patch = _validation_patches(error)
    with semaphore_patch, status_patch:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], changed
        )
    assert result["errors"] == {"base": expected}


@pytest.mark.parametrize(
    "change",
    [
        {CONF_API_TOKEN: ""},
        {"project_id": False},
        {"project_id": "not-an-int"},
        {CONF_POLL_INTERVAL: 1},
        {"verify_ssl": "yes"},
    ],
)
def test_normalize_data_rejects_invalid_scalars(
    config_data: Mapping[str, str | int | bool],
    change: Mapping[str, object],
) -> None:
    """Validation helpers reject empty secrets and out-of-contract scalars."""
    candidate: dict[str, object] = dict(config_data)
    candidate.update(change)
    with pytest.raises((AuthenticationError, ValueError)):
        _normalize_data(candidate)


def test_normalize_data_accepts_numeric_strings(
    config_data: Mapping[str, str | int | bool],
) -> None:
    """Schema-compatible numeric strings normalize into integers."""
    candidate: dict[str, object] = dict(config_data)
    candidate["project_id"] = "7"
    assert _normalize_data(candidate)["project_id"] == 7
