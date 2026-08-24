"""Discover the compatible local Home Assistant App through Supervisor."""

import logging
from dataclasses import dataclass

from aiohasupervisor.exceptions import SupervisorError
from aiohasupervisor.models.addons import AddonState, InstalledAddon, Repository
from homeassistant.components.hassio.const import DATA_COMPONENT
from homeassistant.components.hassio.handler import get_supervisor_client
from homeassistant.core import HomeAssistant
from yarl import URL

from .const import NATIVE_APP_PORT, NATIVE_APP_REPOSITORY, NATIVE_APP_SLUG

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DiscoveredNativeBackend:
    """A compatible App reported by the local Supervisor."""

    name: str
    slug: str
    version: str | None
    state: AddonState
    url: str

    @property
    def is_running(self) -> bool:
        """Return whether the App is ready to accept the integration connection."""
        return self.state is AddonState.STARTED

    @property
    def frontend_url(self) -> str:
        """Return the Home Assistant route used by the App's Open UI action."""
        return f"/app/{self.slug}"


async def async_discover_native_backend(
    hass: HomeAssistant,
) -> DiscoveredNativeBackend | None:
    """Return the installed compatible App without exposing Supervisor credentials."""
    if DATA_COMPONENT not in hass.data:
        return None

    client = get_supervisor_client(hass)
    try:
        addons = await client.addons.list()
    except SupervisorError:
        _LOGGER.debug("Supervisor App discovery is unavailable")
        return None

    candidates = [addon for addon in addons if _matches_app_slug(addon.slug)]
    for addon in candidates:
        if _repository_url_matches(addon.repository):
            return _discovered_backend(addon)
    if not candidates:
        return None

    try:
        repositories = await client.store.repositories_list()
    except SupervisorError:
        _LOGGER.debug("Supervisor repository discovery is unavailable")
        return None

    repositories_by_slug = {repository.slug: repository for repository in repositories}
    for addon in candidates:
        repository = repositories_by_slug.get(addon.repository)
        if repository is not None and _repository_matches(repository):
            return _discovered_backend(addon)
    return None


def _discovered_backend(addon: InstalledAddon) -> DiscoveredNativeBackend:
    """Build the local connection details from verified Supervisor metadata."""
    return DiscoveredNativeBackend(
        name=addon.name,
        slug=addon.slug,
        version=addon.version,
        state=addon.state,
        url=_internal_url(addon.slug),
    )


def _repository_matches(repository: Repository) -> bool:
    """Match a repository ID to its stable public source metadata."""
    return _repository_url_matches(repository.source) or _repository_url_matches(
        repository.url
    )


def _repository_url_matches(value: str) -> bool:
    """Match a repository URL without relying on its installation-specific ID."""
    return _normalize_repository(value) == _normalize_repository(NATIVE_APP_REPOSITORY)


def _matches_app_slug(value: str) -> bool:
    """Accept the plain local slug and Supervisor's repository-prefixed slug."""
    return value == NATIVE_APP_SLUG or value.endswith(f"_{NATIVE_APP_SLUG}")


def _internal_url(addon_identifier: str) -> str:
    """Build the documented internal DNS endpoint from a Supervisor identifier."""
    return f"http://{addon_identifier.replace('_', '-')}:{NATIVE_APP_PORT}"


def _normalize_repository(value: str) -> str:
    """Compare public repository URLs without cosmetic trailing syntax."""
    try:
        url = URL(value.strip())
    except ValueError:
        return ""
    path = url.path.rstrip("/").removesuffix(".git")
    return str(url.with_path(path).with_query(None).with_fragment(None)).lower()
