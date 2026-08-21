"""Asynchronous HTTP adapters for status and Semaphore."""

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Final

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout
from yarl import URL

from ..const import (
    DEFAULT_REQUEST_TIMEOUT,
    MAX_STATUS_RESPONSE_BYTES,
    TASK_TERMINAL_FAILURE,
    TASK_TERMINAL_SUCCESS,
)
from ..domain import Command, HostStatus, SemaphoreTask, TaskPhase
from ..exceptions import (
    AuthenticationError,
    CannotConnectError,
    InvalidProjectError,
    InvalidStatusDataError,
    InvalidUrlError,
    SemaphoreTaskError,
)

_WAITING_STATES: Final = frozenset({"created", "pending", "queued", "waiting"})
_RUNNING_STATES: Final = frozenset({"running", "starting"})


def normalize_url(value: str, *, base: bool) -> str:
    """Validate and normalize a user-provided HTTP URL."""
    try:
        url = URL(value.strip())
    except ValueError as err:
        raise InvalidUrlError("The URL is invalid") from err

    if (
        url.scheme not in {"http", "https"}
        or not url.host
        or url.user is not None
        or url.password is not None
        or url.fragment
    ):
        raise InvalidUrlError("The URL is invalid")
    if url.query:
        raise InvalidUrlError("Configured URLs must not contain a query")

    if not base:
        return str(url)

    path = url.path.rstrip("/")
    if not path:
        path = ""
    return str(url.with_path(path))


def parse_hosts(payload: object) -> dict[str, HostStatus]:
    """Parse an untrusted status payload into immutable host models."""
    if not isinstance(payload, dict):
        raise InvalidStatusDataError("Status data must be an object")

    hosts: dict[str, HostStatus] = {}
    for host_id, raw_host in payload.items():
        if not isinstance(host_id, str) or not host_id.strip() or len(host_id) > 255:
            raise InvalidStatusDataError("A host identifier is invalid")
        if not isinstance(raw_host, dict):
            raise InvalidStatusDataError("A host entry must be an object")

        declared_host = _optional_string(raw_host.get("host"))
        if declared_host is not None and declared_host != host_id:
            raise InvalidStatusDataError("A host identifier is inconsistent")

        checked_at = _timestamp(raw_host.get("checked_at"))
        hosts[host_id] = HostStatus(
            host_id=host_id,
            hostname=_optional_string(raw_host.get("hostname")),
            distribution=_optional_string(raw_host.get("distribution")),
            distribution_version=_optional_string(raw_host.get("distribution_version")),
            kernel=_optional_string(raw_host.get("kernel")),
            updates=_non_negative_integer(raw_host.get("updates"), "updates"),
            security_updates=_non_negative_integer(
                raw_host.get("security_updates"), "security_updates"
            ),
            reboot_required=_boolean(
                raw_host.get("reboot_required"), "reboot_required"
            ),
            status=_optional_string(raw_host.get("status")),
            checked_at=checked_at,
        )
    return hosts


def parse_task(payload: object, *, default_status: str = "waiting") -> SemaphoreTask:
    """Parse a Semaphore task response."""
    if not isinstance(payload, dict):
        raise SemaphoreTaskError("The task response is invalid")

    raw_id = payload.get("id", payload.get("task_id"))
    task_id = _positive_integer(raw_id, "task id", SemaphoreTaskError)
    raw_status_value = payload.get("status", payload.get("state", default_status))
    if not isinstance(raw_status_value, str) or not raw_status_value.strip():
        raise SemaphoreTaskError("The task status is invalid")
    raw_status = raw_status_value.strip().lower()

    if raw_status in _WAITING_STATES:
        phase = TaskPhase.WAITING
    elif raw_status in _RUNNING_STATES:
        phase = TaskPhase.RUNNING
    elif raw_status in TASK_TERMINAL_SUCCESS:
        phase = TaskPhase.SUCCESS
    elif raw_status in TASK_TERMINAL_FAILURE:
        phase = TaskPhase.FAILED
    else:
        phase = TaskPhase.UNKNOWN
    return SemaphoreTask(task_id=task_id, phase=phase, raw_status=raw_status)


class StatusClient:
    """Fetch and normalize all hosts from one status endpoint."""

    def __init__(
        self,
        session: ClientSession,
        status_url: str,
        *,
        verify_ssl: bool = True,
        request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
    ) -> None:
        """Initialize the status adapter."""
        self._session = session
        self._status_url = normalize_url(status_url, base=False)
        self._verify_ssl = verify_ssl
        self._timeout = ClientTimeout(total=request_timeout)

    async def async_validate(self) -> None:
        """Validate connectivity and payload structure."""
        await self.async_get_hosts()

    async def async_get_hosts(self) -> Mapping[str, HostStatus]:
        """Fetch exactly one complete host snapshot."""
        try:
            async with self._session.get(
                self._status_url,
                allow_redirects=False,
                ssl=self._verify_ssl,
                timeout=self._timeout,
            ) as response:
                if response.status < 200 or response.status >= 300:
                    raise CannotConnectError("The status endpoint returned an error")
                payload = await _read_json(response, MAX_STATUS_RESPONSE_BYTES)
        except InvalidStatusDataError:
            raise
        except (TimeoutError, ClientError) as err:
            raise CannotConnectError("The status endpoint cannot be reached") from err
        return parse_hosts(payload)


class SemaphoreClient:
    """Automation backend adapter for the Semaphore task API."""

    def __init__(
        self,
        session: ClientSession,
        base_url: str,
        api_token: str,
        project_id: int,
        template_ids: Mapping[Command, int],
        *,
        verify_ssl: bool = True,
        request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
    ) -> None:
        """Initialize the Semaphore adapter."""
        self._session = session
        self._base_url = normalize_url(base_url, base=True)
        self._api_token = api_token
        self._project_id = project_id
        self._template_ids = dict(template_ids)
        self._verify_ssl = verify_ssl
        self._timeout = ClientTimeout(total=request_timeout)

    async def async_validate(self) -> None:
        """Validate authentication and project access."""
        await self.async_get_project()

    async def async_get_project(self) -> object:
        """Fetch the configured project."""
        return await self._async_request_json(
            "GET", f"/api/project/{self._project_id}", project_lookup=True
        )

    async def async_get_templates(self) -> object:
        """Fetch templates for the configured project."""
        return await self._async_request_json(
            "GET", f"/api/project/{self._project_id}/templates"
        )

    async def async_start_command(
        self, command: Command, host_id: str | None = None
    ) -> SemaphoreTask:
        """Start a configured command task."""
        if command in {Command.UPDATE_HOST, Command.REBOOT_HOST} and host_id is None:
            raise SemaphoreTaskError("This command requires a host")
        if command not in self._template_ids:
            raise SemaphoreTaskError("This command is not configured")

        body: dict[str, int | str] = {"template_id": self._template_ids[command]}
        if host_id is not None:
            body["limit"] = host_id
        payload = await self._async_request_json(
            "POST", f"/api/project/{self._project_id}/tasks", json_body=body
        )
        return parse_task(payload)

    async def async_start_task(
        self, template_id: int, limit: str | None = None
    ) -> SemaphoreTask:
        """Start an arbitrary configured Semaphore template."""
        body: dict[str, int | str] = {"template_id": template_id}
        if limit is not None:
            body["limit"] = limit
        payload = await self._async_request_json(
            "POST", f"/api/project/{self._project_id}/tasks", json_body=body
        )
        return parse_task(payload)

    async def async_get_task(self, task_id: int) -> SemaphoreTask:
        """Fetch one task."""
        payload = await self._async_request_json(
            "GET", f"/api/project/{self._project_id}/tasks/{task_id}"
        )
        return parse_task(payload)

    async def async_get_task_output(self, task_id: int) -> object:
        """Fetch task output without logging its potentially sensitive body."""
        return await self._async_request_json(
            "GET", f"/api/project/{self._project_id}/tasks/{task_id}/output"
        )

    async def _async_request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, int | str] | None = None,
        project_lookup: bool = False,
    ) -> object:
        """Perform one safe JSON request and translate transport errors."""
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._api_token}",
        }
        url = f"{self._base_url}{path}"
        try:
            async with self._session.request(
                method,
                url,
                allow_redirects=False,
                headers=headers,
                json=json_body,
                ssl=self._verify_ssl,
                timeout=self._timeout,
            ) as response:
                if response.status in {401, 403}:
                    raise AuthenticationError("Backend authentication failed")
                if response.status == 404 and project_lookup:
                    raise InvalidProjectError("The backend project does not exist")
                if response.status < 200 or response.status >= 300:
                    raise CannotConnectError("The automation backend returned an error")
                return await _read_json(response, MAX_STATUS_RESPONSE_BYTES)
        except (AuthenticationError, InvalidProjectError, InvalidStatusDataError):
            raise
        except (TimeoutError, ClientError) as err:
            raise CannotConnectError(
                "The automation backend cannot be reached"
            ) from err


async def _read_json(response: ClientResponse, max_bytes: int) -> object:
    """Read a size-limited JSON response without exposing its body."""
    body = await response.read()
    if len(body) > max_bytes:
        raise InvalidStatusDataError("The response is too large")
    try:
        return json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise InvalidStatusDataError("The response is not valid JSON") from err


def _optional_string(value: object) -> str | None:
    """Normalize an optional string value."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidStatusDataError("A text field has an invalid type")
    normalized = value.strip()
    return normalized or None


def _positive_integer(
    value: object,
    field: str,
    error_type: type[InvalidStatusDataError] | type[SemaphoreTaskError],
) -> int:
    """Parse a positive integer without accepting booleans."""
    parsed = _integer(value, field, error_type)
    if parsed < 1:
        raise error_type(f"The {field} must be positive")
    return parsed


def _non_negative_integer(value: object, field: str) -> int:
    """Parse a non-negative integer."""
    parsed = _integer(value, field, InvalidStatusDataError)
    if parsed < 0:
        raise InvalidStatusDataError(f"The {field} must not be negative")
    return parsed


def _integer(
    value: object,
    field: str,
    error_type: type[InvalidStatusDataError] | type[SemaphoreTaskError],
) -> int:
    """Parse an integer-compatible JSON value."""
    if isinstance(value, bool):
        raise error_type(f"The {field} is invalid")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped and stripped.lstrip("-").isdigit():
            return int(stripped)
    raise error_type(f"The {field} is invalid")


def _boolean(value: object, field: str) -> bool:
    """Parse a robust but unambiguous boolean value."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise InvalidStatusDataError(f"The {field} is invalid")


def _timestamp(value: object) -> datetime:
    """Parse a required timezone-aware ISO-8601 timestamp."""
    if not isinstance(value, str) or not value.strip():
        raise InvalidStatusDataError("The checked_at timestamp is invalid")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as err:
        raise InvalidStatusDataError("The checked_at timestamp is invalid") from err
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InvalidStatusDataError("The checked_at timestamp needs a timezone")
    return parsed
