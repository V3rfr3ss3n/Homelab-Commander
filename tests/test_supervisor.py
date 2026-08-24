"""Tests for optional local Home Assistant App discovery."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiohasupervisor.exceptions import SupervisorConnectionError
from aiohasupervisor.models.addons import AddonState
from homeassistant.components.hassio.const import DATA_COMPONENT
from homeassistant.core import HomeAssistant

from custom_components.homelab_updates.supervisor import (
    _internal_url,
    async_discover_native_backend,
)

REPOSITORY_ID = "synthetic_repository"
REPOSITORY_URL = "https://github.com/V3rfr3ss3n/Homelab-Commander"


def _addon(
    *,
    slug: str = f"{REPOSITORY_ID}_homelab_updates",
    repository: str = REPOSITORY_ID,
    state: AddonState = AddonState.STARTED,
    name: str = "Unexpected display name",
) -> SimpleNamespace:
    """Build the Supervisor fields the discovery boundary consumes."""
    return SimpleNamespace(
        slug=slug,
        repository=repository,
        state=state,
        name=name,
        version="0.3.0-dev.0",
    )


def _repository(*, source: str = REPOSITORY_URL) -> SimpleNamespace:
    """Build read-only Supervisor repository metadata."""
    return SimpleNamespace(
        slug=REPOSITORY_ID,
        source=source,
        url=source,
    )


def _client(
    addons: list[SimpleNamespace],
    repositories: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    """Build the installed-App and repository Supervisor clients."""
    return SimpleNamespace(
        addons=SimpleNamespace(list=AsyncMock(return_value=addons)),
        store=SimpleNamespace(
            repositories_list=AsyncMock(
                return_value=repositories
                if repositories is not None
                else [_repository()]
            )
        ),
    )


async def test_discovery_uses_stable_slug_and_repository_identity(
    hass: HomeAssistant,
) -> None:
    """A renamed App is still detected and its DNS endpoint is derived."""
    hass.data[DATA_COMPONENT] = object()
    client = _client([_addon()])

    with patch(
        "custom_components.homelab_updates.supervisor.get_supervisor_client",
        return_value=client,
    ):
        discovered = await async_discover_native_backend(hass)

    assert discovered is not None
    assert discovered.name == "Unexpected display name"
    assert discovered.slug == f"{REPOSITORY_ID}_homelab_updates"
    assert discovered.url == "http://synthetic-repository-homelab-updates:8099"
    assert discovered.frontend_url == f"/app/{REPOSITORY_ID}_homelab_updates"
    assert discovered.is_running
    client.store.repositories_list.assert_awaited_once()


async def test_discovery_rejects_matching_slug_from_other_repository(
    hass: HomeAssistant,
) -> None:
    """The common slug alone cannot select another vendor's App."""
    hass.data[DATA_COMPONENT] = object()
    client = _client([_addon()], [_repository(source="https://example.invalid/other")])

    with patch(
        "custom_components.homelab_updates.supervisor.get_supervisor_client",
        return_value=client,
    ):
        assert await async_discover_native_backend(hass) is None


async def test_discovery_reports_stopped_app_without_connecting(
    hass: HomeAssistant,
) -> None:
    """A stopped matching App leads to the manual fallback in the flow."""
    hass.data[DATA_COMPONENT] = object()
    client = _client([_addon(state=AddonState.STOPPED)])

    with patch(
        "custom_components.homelab_updates.supervisor.get_supervisor_client",
        return_value=client,
    ):
        discovered = await async_discover_native_backend(hass)

    assert discovered is not None
    assert not discovered.is_running


async def test_discovery_handles_missing_or_unavailable_supervisor(
    hass: HomeAssistant,
) -> None:
    """Core, Container, and unavailable Supervisor installations fall back safely."""
    assert await async_discover_native_backend(hass) is None

    hass.data[DATA_COMPONENT] = object()
    client = SimpleNamespace(
        addons=SimpleNamespace(list=AsyncMock(side_effect=SupervisorConnectionError()))
    )
    with patch(
        "custom_components.homelab_updates.supervisor.get_supervisor_client",
        return_value=client,
    ):
        assert await async_discover_native_backend(hass) is None


async def test_discovery_accepts_direct_repository_url_without_store_lookup(
    hass: HomeAssistant,
) -> None:
    """Newer Supervisor payloads may expose the public source URL directly."""
    hass.data[DATA_COMPONENT] = object()
    client = _client([_addon(repository=f"{REPOSITORY_URL}.git")])

    with patch(
        "custom_components.homelab_updates.supervisor.get_supervisor_client",
        return_value=client,
    ):
        assert await async_discover_native_backend(hass) is not None

    client.store.repositories_list.assert_not_awaited()


async def test_discovery_falls_back_when_repository_lookup_is_unavailable(
    hass: HomeAssistant,
) -> None:
    """An unresolved repository ID is never accepted on slug alone."""
    hass.data[DATA_COMPONENT] = object()
    client = _client([_addon()])
    client.store.repositories_list.side_effect = SupervisorConnectionError()

    with patch(
        "custom_components.homelab_updates.supervisor.get_supervisor_client",
        return_value=client,
    ):
        assert await async_discover_native_backend(hass) is None


def test_internal_url_replaces_supervisor_identifier_underscores() -> None:
    """App DNS follows the documented underscore-to-hyphen conversion."""
    assert _internal_url("repository_identifier_homelab_updates") == (
        "http://repository-identifier-homelab-updates:8099"
    )
