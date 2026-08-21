"""Config flow, duplicate, reauth, and reconfigure tests."""

from collections.abc import Mapping
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.homelab_updates.config_flow import _normalize_data
from custom_components.homelab_updates.const import (
    CONF_POLL_INTERVAL,
    CONF_SEMAPHORE_URL,
    DOMAIN,
)
from custom_components.homelab_updates.exceptions import (
    AuthenticationError,
    CannotConnectError,
    InvalidProjectError,
    InvalidStatusDataError,
)


def _validation_patches(
    semaphore_error: Exception | None = None,
    status_error: Exception | None = None,
) -> tuple[patch, patch]:
    return (
        patch(
            "custom_components.homelab_updates.config_flow.SemaphoreClient.async_validate",
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
            user_input=dict(config_data),
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_TOKEN] == config_data[CONF_API_TOKEN]
    assert result["title"] == "semaphore.example.invalid"


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
