"""UI configuration flows for Homelab Updates providers."""

import logging
from collections.abc import Mapping

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .adapters import NativeBackendClient, SemaphoreClient, StatusClient, normalize_url
from .const import (
    BACKEND_NATIVE,
    BACKEND_SEMAPHORE,
    CONF_BACKEND_TYPE,
    CONF_BACKEND_URL,
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
    """Configure a native or legacy Homelab Updates provider."""

    VERSION = 2
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: Mapping[str, object] | None = None
    ) -> FlowResult:
        """Choose a provider before collecting provider-specific settings."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_BACKEND_TYPE, default=BACKEND_NATIVE): vol.In([
                        BACKEND_NATIVE,
                        BACKEND_SEMAPHORE,
                    ])
                }),
            )
        if CONF_SEMAPHORE_URL in user_input:
            return await self.async_step_semaphore(user_input)
        if CONF_BACKEND_URL in user_input:
            return await self.async_step_native(user_input)
        backend_type = user_input.get(CONF_BACKEND_TYPE)
        if backend_type == BACKEND_NATIVE:
            return await self.async_step_native()
        if backend_type == BACKEND_SEMAPHORE:
            return await self.async_step_semaphore()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_BACKEND_TYPE): vol.In([
                    BACKEND_NATIVE,
                    BACKEND_SEMAPHORE,
                ])
            }),
            errors={"base": "unknown"},
        )

    async def async_step_native(
        self, user_input: Mapping[str, object] | None = None
    ) -> FlowResult:
        """Configure the native backend."""
        return await self._async_provider_step(
            BACKEND_NATIVE, "native", user_input, _native_schema(user_input)
        )

    async def async_step_semaphore(
        self, user_input: Mapping[str, object] | None = None
    ) -> FlowResult:
        """Configure the optional Semaphore legacy provider."""
        return await self._async_provider_step(
            BACKEND_SEMAPHORE,
            "semaphore",
            user_input,
            _semaphore_schema(user_input),
        )

    async def _async_provider_step(
        self,
        backend_type: str,
        step_id: str,
        user_input: Mapping[str, object] | None,
        schema: vol.Schema,
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            candidate = {**user_input, CONF_BACKEND_TYPE: backend_type}
            try:
                data = await self._async_validate_and_normalize(candidate)
            except Exception as err:  # Payloads are never included in UI errors.
                errors["base"] = _flow_error(err)
                if errors["base"] == "unknown":
                    _LOGGER.exception("Unexpected exception during configuration")
            else:
                await self.async_set_unique_id(_unique_id(data))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=_entry_title(data), data=data)
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, object]) -> FlowResult:
        """Start reauthentication for an existing entry."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Mapping[str, object] | None = None
    ) -> FlowResult:
        """Validate and store a replacement provider token."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = dict(entry.data)
            data[CONF_API_TOKEN] = _required_string(user_input, CONF_API_TOKEN)
            data.setdefault(CONF_BACKEND_TYPE, BACKEND_SEMAPHORE)
            try:
                normalized = await self._async_validate_and_normalize(
                    data, validate_status=False
                )
            except Exception as err:
                error = _flow_error(err)
                errors["base"] = (
                    error if error in {"invalid_auth", "cannot_connect"} else "unknown"
                )
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates=normalized
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: Mapping[str, object] | None = None
    ) -> FlowResult:
        """Update settings without changing the selected provider."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        backend_type = str(entry.data.get(CONF_BACKEND_TYPE, BACKEND_SEMAPHORE))
        if user_input is not None:
            candidate = {
                **user_input,
                CONF_API_TOKEN: entry.data[CONF_API_TOKEN],
                CONF_BACKEND_TYPE: backend_type,
            }
            try:
                data = await self._async_validate_and_normalize(candidate)
            except Exception as err:
                errors["base"] = _flow_error(err)
                if errors["base"] == "unknown":
                    _LOGGER.exception("Unexpected exception during reconfiguration")
            else:
                unique_id = _unique_id(data)
                for other in self.hass.config_entries.async_entries(DOMAIN):
                    if (
                        other.entry_id != entry.entry_id
                        and other.unique_id == unique_id
                    ):
                        return self.async_abort(reason="already_configured")
                return self.async_update_reload_and_abort(
                    entry, data_updates=data, unique_id=unique_id
                )
        defaults = {
            key: value for key, value in entry.data.items() if key != CONF_API_TOKEN
        }
        schema = (
            _native_schema(defaults, include_token=False)
            if backend_type == BACKEND_NATIVE
            else _semaphore_schema(defaults, include_token=False)
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )

    async def _async_validate_and_normalize(
        self,
        raw: Mapping[str, object],
        *,
        validate_status: bool = True,
    ) -> FlowData:
        backend_type = raw.get(CONF_BACKEND_TYPE, BACKEND_SEMAPHORE)
        session = async_get_clientsession(self.hass)
        if backend_type == BACKEND_NATIVE:
            data = _normalize_native_data(raw)
            client = NativeBackendClient(
                session,
                str(data[CONF_BACKEND_URL]),
                str(data[CONF_API_TOKEN]),
                verify_ssl=bool(data[CONF_VERIFY_SSL]),
            )
            await client.async_validate()
            return data
        data = _normalize_data(raw)
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


def _native_schema(
    defaults: Mapping[str, object] | None, *, include_token: bool = True
) -> vol.Schema:
    values = defaults or {}
    schema: dict[vol.Marker, object] = {
        vol.Required(CONF_BACKEND_URL, default=values.get(CONF_BACKEND_URL, "")): str,
        vol.Required(
            CONF_POLL_INTERVAL,
            default=values.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        ): vol.All(
            vol.Coerce(int),
            vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL),
        ),
        vol.Required(CONF_VERIFY_SSL, default=values.get(CONF_VERIFY_SSL, True)): bool,
    }
    if include_token:
        schema[vol.Required(CONF_API_TOKEN)] = str
    return vol.Schema(schema)


def _semaphore_schema(
    defaults: Mapping[str, object] | None, *, include_token: bool = True
) -> vol.Schema:
    values = defaults or {}
    schema: dict[vol.Marker, object] = {
        vol.Required(
            CONF_SEMAPHORE_URL, default=values.get(CONF_SEMAPHORE_URL, "")
        ): str,
        vol.Required(CONF_PROJECT_ID, default=values.get(CONF_PROJECT_ID, 1)): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
        vol.Required(CONF_STATUS_URL, default=values.get(CONF_STATUS_URL, "")): str,
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
        vol.Required(CONF_VERIFY_SSL, default=values.get(CONF_VERIFY_SSL, True)): bool,
    }
    if include_token:
        schema[vol.Required(CONF_API_TOKEN)] = str
    return vol.Schema(schema)


def _normalize_native_data(raw: Mapping[str, object]) -> FlowData:
    token = _required_string(raw, CONF_API_TOKEN)
    if not token:
        raise AuthenticationError("An API token is required")
    return {
        CONF_BACKEND_TYPE: BACKEND_NATIVE,
        CONF_BACKEND_URL: normalize_url(
            _required_string(raw, CONF_BACKEND_URL), base=True
        ),
        CONF_API_TOKEN: token,
        CONF_POLL_INTERVAL: _bounded_poll_interval(raw),
        CONF_VERIFY_SSL: _required_bool(raw, CONF_VERIFY_SSL),
    }


def _normalize_data(raw: Mapping[str, object]) -> FlowData:
    """Normalize the pre-0.2 Semaphore configuration contract."""
    token = _required_string(raw, CONF_API_TOKEN)
    if not token:
        raise AuthenticationError("An API token is required")
    return {
        CONF_BACKEND_TYPE: BACKEND_SEMAPHORE,
        CONF_SEMAPHORE_URL: normalize_url(
            _required_string(raw, CONF_SEMAPHORE_URL), base=True
        ),
        CONF_API_TOKEN: token,
        CONF_PROJECT_ID: _positive_int(raw, CONF_PROJECT_ID),
        CONF_STATUS_URL: normalize_url(
            _required_string(raw, CONF_STATUS_URL), base=False
        ),
        CONF_CHECK_TEMPLATE_ID: _positive_int(raw, CONF_CHECK_TEMPLATE_ID),
        CONF_UPDATE_TEMPLATE_ID: _positive_int(raw, CONF_UPDATE_TEMPLATE_ID),
        CONF_REBOOT_TEMPLATE_ID: _positive_int(raw, CONF_REBOOT_TEMPLATE_ID),
        CONF_EXPORT_TEMPLATE_ID: _positive_int(raw, CONF_EXPORT_TEMPLATE_ID),
        CONF_POLL_INTERVAL: _bounded_poll_interval(raw),
        CONF_VERIFY_SSL: _required_bool(raw, CONF_VERIFY_SSL),
    }


def _template_ids(data: Mapping[str, str | int | bool]) -> dict[Command, int]:
    return {
        Command.CHECK_ALL: int(data[CONF_CHECK_TEMPLATE_ID]),
        Command.UPDATE_HOST: int(data[CONF_UPDATE_TEMPLATE_ID]),
        Command.REBOOT_HOST: int(data[CONF_REBOOT_TEMPLATE_ID]),
        Command.REFRESH_STATUS: int(data[CONF_EXPORT_TEMPLATE_ID]),
    }


def _unique_id(data: Mapping[str, str | int | bool]) -> str:
    if data[CONF_BACKEND_TYPE] == BACKEND_NATIVE:
        return f"native|{data[CONF_BACKEND_URL]}"
    return f"{data[CONF_SEMAPHORE_URL]}|{data[CONF_PROJECT_ID]}"


def _entry_title(data: Mapping[str, str | int | bool]) -> str:
    from yarl import URL

    url_key = (
        CONF_BACKEND_URL
        if data[CONF_BACKEND_TYPE] == BACKEND_NATIVE
        else CONF_SEMAPHORE_URL
    )
    return URL(str(data[url_key])).host or "Homelab Updates"


def _flow_error(err: Exception) -> str:
    if isinstance(err, InvalidUrlError):
        return "invalid_url"
    if isinstance(err, AuthenticationError):
        return "invalid_auth"
    if isinstance(err, InvalidProjectError):
        return "invalid_project"
    if isinstance(err, InvalidStatusDataError):
        return "invalid_status_data"
    if isinstance(err, CannotConnectError):
        return "cannot_connect"
    return "unknown"


def _required_string(raw: Mapping[str, object], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str):
        raise InvalidUrlError("A required text value is invalid")
    return value.strip()


def _positive_int(raw: Mapping[str, object], key: str) -> int:
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
    value = _positive_int(raw, CONF_POLL_INTERVAL)
    if not MIN_POLL_INTERVAL <= value <= MAX_POLL_INTERVAL:
        raise ValueError("poll_interval is outside the supported range")
    return value


def _required_bool(raw: Mapping[str, object], key: str) -> bool:
    value = raw.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value
