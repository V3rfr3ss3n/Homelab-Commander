"""UI configuration flows for Homelab Updates."""

import logging
from collections.abc import Mapping

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .adapters import SemaphoreClient, StatusClient, normalize_url
from .const import (
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
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)
from .domain import Command
from .exceptions import (
    AuthenticationError,
    CannotConnectError,
    InvalidProjectError,
    InvalidStatusDataError,
    InvalidUrlError,
)

_LOGGER = logging.getLogger(__name__)

type FlowData = dict[str, str | int | bool]
type FlowResult = config_entries.ConfigFlowResult


class HomelabUpdatesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a Homelab Updates config entry."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: Mapping[str, object] | None = None
    ) -> FlowResult:
        """Create a new config entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data = await self._async_validate_and_normalize(user_input)
            except InvalidUrlError:
                errors["base"] = "invalid_url"
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except InvalidProjectError:
                errors["base"] = "invalid_project"
            except InvalidStatusDataError:
                errors["base"] = "invalid_status_data"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during configuration")
                errors["base"] = "unknown"
            else:
                unique_id = _unique_id(data)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=_entry_title(data),
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_full_schema(user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, object]) -> FlowResult:
        """Start reauthentication for an existing entry."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Mapping[str, object] | None = None
    ) -> FlowResult:
        """Validate and store a replacement API token."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = dict(entry.data)
            data[CONF_API_TOKEN] = _required_string(user_input, CONF_API_TOKEN)
            try:
                normalized = await self._async_validate_and_normalize(
                    data,
                    validate_status=False,
                )
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except (InvalidProjectError, InvalidStatusDataError, InvalidUrlError):
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=normalized,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: Mapping[str, object] | None = None
    ) -> FlowResult:
        """Update non-secret config entry settings."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            candidate = dict(user_input)
            candidate[CONF_API_TOKEN] = entry.data[CONF_API_TOKEN]
            try:
                data = await self._async_validate_and_normalize(candidate)
            except InvalidUrlError:
                errors["base"] = "invalid_url"
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except InvalidProjectError:
                errors["base"] = "invalid_project"
            except InvalidStatusDataError:
                errors["base"] = "invalid_status_data"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during reconfiguration")
                errors["base"] = "unknown"
            else:
                unique_id = _unique_id(data)
                for other in self.hass.config_entries.async_entries(DOMAIN):
                    if (
                        other.entry_id != entry.entry_id
                        and other.unique_id == unique_id
                    ):
                        return self.async_abort(reason="already_configured")
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=data,
                    unique_id=unique_id,
                )

        defaults = {
            key: value for key, value in entry.data.items() if key != CONF_API_TOKEN
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_full_schema(defaults, include_token=False),
            errors=errors,
        )

    async def _async_validate_and_normalize(
        self,
        raw: Mapping[str, object],
        *,
        validate_status: bool = True,
    ) -> FlowData:
        """Normalize input and validate both independent services."""
        data = _normalize_data(raw)
        session = async_get_clientsession(self.hass)
        semaphore = SemaphoreClient(
            session,
            str(data[CONF_SEMAPHORE_URL]),
            str(data[CONF_API_TOKEN]),
            int(data[CONF_PROJECT_ID]),
            _template_ids(data),
            verify_ssl=bool(data[CONF_VERIFY_SSL]),
        )
        status = StatusClient(
            session,
            str(data[CONF_STATUS_URL]),
            verify_ssl=bool(data[CONF_VERIFY_SSL]),
        )
        await semaphore.async_validate()
        if validate_status:
            await status.async_validate()
        return data


def _full_schema(
    defaults: Mapping[str, object] | None,
    *,
    include_token: bool = True,
) -> vol.Schema:
    """Build the translated configuration schema."""
    values = defaults or {}
    schema: dict[vol.Marker, object] = {
        vol.Required(
            CONF_SEMAPHORE_URL,
            default=values.get(CONF_SEMAPHORE_URL, ""),
        ): str,
        vol.Required(
            CONF_PROJECT_ID,
            default=values.get(CONF_PROJECT_ID, 1),
        ): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required(
            CONF_STATUS_URL,
            default=values.get(CONF_STATUS_URL, ""),
        ): str,
        vol.Required(
            CONF_CHECK_TEMPLATE_ID,
            default=values.get(CONF_CHECK_TEMPLATE_ID, DEFAULT_CHECK_TEMPLATE_ID),
        ): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required(
            CONF_UPDATE_TEMPLATE_ID,
            default=values.get(CONF_UPDATE_TEMPLATE_ID, DEFAULT_UPDATE_TEMPLATE_ID),
        ): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required(
            CONF_REBOOT_TEMPLATE_ID,
            default=values.get(CONF_REBOOT_TEMPLATE_ID, DEFAULT_REBOOT_TEMPLATE_ID),
        ): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required(
            CONF_EXPORT_TEMPLATE_ID,
            default=values.get(CONF_EXPORT_TEMPLATE_ID, DEFAULT_EXPORT_TEMPLATE_ID),
        ): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required(
            CONF_POLL_INTERVAL,
            default=values.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        ): vol.All(
            vol.Coerce(int),
            vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL),
        ),
        vol.Required(
            CONF_VERIFY_SSL,
            default=values.get(CONF_VERIFY_SSL, True),
        ): bool,
    }
    if include_token:
        schema[vol.Required(CONF_API_TOKEN)] = str
    return vol.Schema(schema)


def _normalize_data(raw: Mapping[str, object]) -> FlowData:
    """Return a typed, normalized config entry payload."""
    semaphore_url = normalize_url(_required_string(raw, CONF_SEMAPHORE_URL), base=True)
    status_url = normalize_url(_required_string(raw, CONF_STATUS_URL), base=False)
    token = _required_string(raw, CONF_API_TOKEN)
    if not token:
        raise AuthenticationError("An API token is required")
    return {
        CONF_SEMAPHORE_URL: semaphore_url,
        CONF_API_TOKEN: token,
        CONF_PROJECT_ID: _positive_int(raw, CONF_PROJECT_ID),
        CONF_STATUS_URL: status_url,
        CONF_CHECK_TEMPLATE_ID: _positive_int(raw, CONF_CHECK_TEMPLATE_ID),
        CONF_UPDATE_TEMPLATE_ID: _positive_int(raw, CONF_UPDATE_TEMPLATE_ID),
        CONF_REBOOT_TEMPLATE_ID: _positive_int(raw, CONF_REBOOT_TEMPLATE_ID),
        CONF_EXPORT_TEMPLATE_ID: _positive_int(raw, CONF_EXPORT_TEMPLATE_ID),
        CONF_POLL_INTERVAL: _bounded_poll_interval(raw),
        CONF_VERIFY_SSL: _required_bool(raw, CONF_VERIFY_SSL),
    }


def _template_ids(data: Mapping[str, str | int | bool]) -> dict[Command, int]:
    """Build command-to-template configuration."""
    return {
        Command.CHECK_ALL: int(data[CONF_CHECK_TEMPLATE_ID]),
        Command.UPDATE_HOST: int(data[CONF_UPDATE_TEMPLATE_ID]),
        Command.REBOOT_HOST: int(data[CONF_REBOOT_TEMPLATE_ID]),
        Command.REFRESH_STATUS: int(data[CONF_EXPORT_TEMPLATE_ID]),
    }


def _unique_id(data: Mapping[str, str | int | bool]) -> str:
    """Return the stable backend/project identity for duplicate detection."""
    return f"{data[CONF_SEMAPHORE_URL]}|{data[CONF_PROJECT_ID]}"


def _entry_title(data: Mapping[str, str | int | bool]) -> str:
    """Return a non-secret title derived from the configured backend host."""
    from yarl import URL

    return URL(str(data[CONF_SEMAPHORE_URL])).host or "Homelab Updates"


def _required_string(raw: Mapping[str, object], key: str) -> str:
    """Read and trim a required string."""
    value = raw.get(key)
    if not isinstance(value, str):
        raise InvalidUrlError("A required text value is invalid")
    return value.strip()


def _positive_int(raw: Mapping[str, object], key: str) -> int:
    """Read a positive integer after schema validation."""
    value = raw.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        parsed = value
    elif isinstance(value, str) and value.strip().isdigit():
        parsed = int(value)
    else:
        raise ValueError(f"{key} must be a positive integer")
    if parsed < 1:
        raise ValueError(f"{key} must be a positive integer")
    return parsed


def _bounded_poll_interval(raw: Mapping[str, object]) -> int:
    """Read and validate the coordinator interval."""
    value = _positive_int(raw, CONF_POLL_INTERVAL)
    if not MIN_POLL_INTERVAL <= value <= MAX_POLL_INTERVAL:
        raise ValueError("poll_interval is outside the supported range")
    return value


def _required_bool(raw: Mapping[str, object], key: str) -> bool:
    """Read a strict boolean configuration value."""
    value = raw.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value
