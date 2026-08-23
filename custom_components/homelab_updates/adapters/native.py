"""HTTP adapter for the native Homelab Updates backend API."""

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Final
from uuid import UUID

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout

from ..const import DEFAULT_REQUEST_TIMEOUT, MAX_STATUS_RESPONSE_BYTES
from ..domain import (
    BackendJobLog,
    BackendTask,
    CustomTaskDefinition,
    HostStatus,
    TaskId,
    TaskPhase,
)
from ..exceptions import (
    AuthenticationError,
    BackendTaskError,
    CannotConnectError,
    InvalidStatusDataError,
)
from .http import normalize_url

_BATCH_PREFIX: Final = "batch:"


class NativeBackendClient:
    """Implement host and automation protocols against the native v1 API."""

    def __init__(
        self,
        session: ClientSession,
        base_url: str,
        api_token: str,
        *,
        verify_ssl: bool = True,
        request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
    ) -> None:
        self._session = session
        self._base_url = normalize_url(base_url, base=True)
        self._api_token = api_token
        self._verify_ssl = verify_ssl
        self._timeout = ClientTimeout(total=request_timeout)

    async def async_validate(self) -> None:
        """Validate authentication and API compatibility."""
        payload = await self._async_request_json("GET", "/api/v1/info")
        if not isinstance(payload, dict) or payload.get("api_version") != "v1":
            raise InvalidStatusDataError("The native backend API is incompatible")

    async def async_get_hosts(self) -> Mapping[str, HostStatus]:
        """Fetch the complete native host snapshot."""
        payload = await self._async_request_json("GET", "/api/v1/hosts")
        if not isinstance(payload, list):
            raise InvalidStatusDataError("The native host response is invalid")
        hosts: dict[str, HostStatus] = {}
        for item in payload:
            host = _parse_host(item)
            if host.host_id in hosts:
                raise InvalidStatusDataError("A native host identity is duplicated")
            hosts[host.host_id] = host
        return hosts

    async def async_check_hosts(self) -> BackendTask:
        """Queue one explicit status job per managed host."""
        payload = await self._async_request_json("POST", "/api/v1/actions/check")
        if not isinstance(payload, list):
            raise BackendTaskError("The native batch task response is invalid")
        tasks = tuple(self._parse_job(item) for item in payload)
        return _batch_task(tasks)

    async def async_refresh_hosts(self) -> BackendTask:
        """Refresh native state through the same safe check operation."""
        return await self.async_check_hosts()

    async def async_update_host(self, host_id: str) -> BackendTask:
        """Queue an update for one canonical host UUID."""
        return await self._async_host_action(host_id, "update")

    async def async_reboot_host(self, host_id: str) -> BackendTask:
        """Queue a reboot for one canonical host UUID."""
        return await self._async_host_action(host_id, "reboot")

    async def async_run_task(self, task_id: str, host_id: str) -> BackendTask:
        """Queue one configured custom task for one canonical host UUID."""
        canonical_host = _uuid(host_id, "host")
        canonical_task = _uuid(task_id, "custom task")
        payload = await self._async_request_json(
            "POST",
            f"/api/v1/hosts/{canonical_host}/actions/tasks/{canonical_task}",
        )
        return self._parse_job(payload)

    async def async_get_task(self, task_id: TaskId) -> BackendTask:
        """Fetch a UUID job or aggregate an in-memory batch handle."""
        value = str(task_id)
        if value.startswith(_BATCH_PREFIX):
            ids = tuple(
                part for part in value.removeprefix(_BATCH_PREFIX).split(",") if part
            )
            if not ids:
                return BackendTask(value, TaskPhase.SUCCESS, "success")
            tasks = tuple([await self._async_get_single(job_id) for job_id in ids])
            return _batch_task(tasks)
        return await self._async_get_single(_uuid(value, "job"))

    async def async_get_tasks(self) -> tuple[BackendTask, ...]:
        """Fetch recent native jobs."""
        payload = await self._async_request_json("GET", "/api/v1/jobs")
        if not isinstance(payload, list):
            raise BackendTaskError("The native job list response is invalid")
        return tuple(self._parse_job(item) for item in payload)

    async def async_get_job_log(self, job_id: str) -> BackendJobLog:
        """Fetch a bounded redacted log without exposing credentials in its URL."""
        canonical = _uuid(job_id, "job")
        payload = await self._async_request_json(
            "GET", f"/api/v1/jobs/{canonical}/log", not_found="Job log not found"
        )
        if not isinstance(payload, dict):
            raise BackendTaskError("The native job log response is invalid")
        returned_id = _uuid_field(payload, "job_id", BackendTaskError)
        output = payload.get("output")
        truncated = payload.get("truncated")
        if not isinstance(output, str) or not isinstance(truncated, bool):
            raise BackendTaskError("The native job log response is invalid")
        return BackendJobLog(returned_id, output, truncated)

    async def async_get_custom_tasks(self) -> tuple[CustomTaskDefinition, ...]:
        """Fetch safe custom-task metadata for dynamic entity discovery."""
        payload = await self._async_request_json("GET", "/api/v1/custom-tasks")
        if not isinstance(payload, list):
            raise BackendTaskError("The native custom task response is invalid")
        return tuple(_parse_custom_task(item) for item in payload)

    async def _async_host_action(self, host_id: str, action: str) -> BackendTask:
        canonical = _uuid(host_id, "host")
        payload = await self._async_request_json(
            "POST", f"/api/v1/hosts/{canonical}/actions/{action}"
        )
        return self._parse_job(payload)

    async def _async_get_single(self, job_id: str) -> BackendTask:
        payload = await self._async_request_json("GET", f"/api/v1/jobs/{job_id}")
        return self._parse_job(payload)

    def _parse_job(self, payload: object) -> BackendTask:
        return _parse_job(payload, base_url=self._base_url)

    async def _async_request_json(
        self, method: str, path: str, *, not_found: str | None = None
    ) -> object:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._api_token}",
        }
        try:
            async with self._session.request(
                method,
                f"{self._base_url}{path}",
                allow_redirects=False,
                headers=headers,
                ssl=self._verify_ssl,
                timeout=self._timeout,
            ) as response:
                if response.status in {401, 403}:
                    raise AuthenticationError("Native backend authentication failed")
                if response.status == 404 and not_found is not None:
                    raise BackendTaskError(not_found)
                if response.status < 200 or response.status >= 300:
                    raise CannotConnectError("The native backend returned an error")
                return await _read_json(response)
        except AuthenticationError, BackendTaskError, InvalidStatusDataError:
            raise
        except (TimeoutError, ClientError) as err:
            raise CannotConnectError("The native backend cannot be reached") from err


async def _read_json(response: ClientResponse) -> object:
    body = await response.read()
    if len(body) > MAX_STATUS_RESPONSE_BYTES:
        raise InvalidStatusDataError("The native backend response is too large")
    try:
        return json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise InvalidStatusDataError("The native backend response is invalid") from err


def _parse_host(payload: object) -> HostStatus:
    if not isinstance(payload, dict):
        raise InvalidStatusDataError("A native host entry is invalid")
    host_id = _uuid_field(payload, "id")
    return HostStatus(
        host_id=host_id,
        hostname=_optional_text(payload, "name"),
        distribution=_optional_text(payload, "distribution"),
        distribution_version=_optional_text(payload, "distribution_version"),
        kernel=_optional_text(payload, "kernel"),
        updates=_non_negative_int(payload, "updates"),
        security_updates=_non_negative_int(payload, "security_updates"),
        reboot_required=_bool(payload, "reboot_required"),
        status=_optional_text(payload, "status"),
        checked_at=_optional_datetime(payload, "checked_at"),
    )


def _parse_job(payload: object, *, base_url: str | None = None) -> BackendTask:
    if not isinstance(payload, dict):
        raise BackendTaskError("A native job response is invalid")
    task_id = _uuid_field(payload, "id", BackendTaskError)
    raw_state = payload.get("state")
    if not isinstance(raw_state, str):
        raise BackendTaskError("A native job state is invalid")
    phases = {
        "queued": TaskPhase.WAITING,
        "running": TaskPhase.RUNNING,
        "success": TaskPhase.SUCCESS,
        "failed": TaskPhase.FAILED,
        "cancelled": TaskPhase.CANCELLED,
    }
    phase = phases.get(raw_state, TaskPhase.UNKNOWN)
    return BackendTask(
        task_id=task_id,
        phase=phase,
        raw_status=raw_state,
        action=_optional_text(payload, "action", BackendTaskError),
        host_id=_optional_uuid_field(payload, "host_id", BackendTaskError),
        host_name=_optional_text(payload, "host_name", BackendTaskError),
        created_at=_optional_datetime(payload, "created_at", BackendTaskError),
        started_at=_optional_datetime(payload, "started_at", BackendTaskError),
        finished_at=_optional_datetime(payload, "finished_at", BackendTaskError),
        exit_code=_optional_int(payload, "exit_code", BackendTaskError),
        error_code=_optional_text(payload, "error_code", BackendTaskError),
        short_error=_optional_text(payload, "short_error", BackendTaskError),
        duration=_optional_number(payload, "duration", BackendTaskError),
        log_available=_optional_bool(payload, "log_available", BackendTaskError)
        or False,
        job_url=f"{base_url.rstrip('/')}/#/jobs/{task_id}" if base_url else None,
        reboot_required=_optional_bool(payload, "reboot_required", BackendTaskError),
    )


def _batch_task(tasks: tuple[BackendTask, ...]) -> BackendTask:
    task_id = _BATCH_PREFIX + ",".join(str(task.task_id) for task in tasks)
    if any(task.phase is TaskPhase.FAILED for task in tasks):
        phase = TaskPhase.FAILED
    elif tasks and all(task.phase is TaskPhase.SUCCESS for task in tasks):
        phase = TaskPhase.SUCCESS
    elif any(task.phase is TaskPhase.RUNNING for task in tasks):
        phase = TaskPhase.RUNNING
    elif tasks:
        phase = TaskPhase.WAITING
    else:
        phase = TaskPhase.SUCCESS
    return BackendTask(task_id=task_id, phase=phase, raw_status=phase.value)


def _parse_custom_task(payload: object) -> CustomTaskDefinition:
    if not isinstance(payload, dict):
        raise BackendTaskError("A native custom task is invalid")
    task_id = _uuid_field(payload, "id", BackendTaskError)
    name = _optional_text(payload, "name", BackendTaskError)
    enabled = payload.get("enabled")
    if name is None or not isinstance(enabled, bool):
        raise BackendTaskError("A native custom task is invalid")
    return CustomTaskDefinition(
        task_id=task_id,
        name=name,
        description=_optional_text(payload, "description", BackendTaskError),
        enabled=enabled,
    )


def _uuid(value: object, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, AttributeError) as err:
        raise BackendTaskError(f"The native {field} identity is invalid") from err


def _uuid_field(
    payload: dict[object, object],
    field: str,
    error_type: type[InvalidStatusDataError]
    | type[BackendTaskError] = InvalidStatusDataError,
) -> str:
    try:
        return str(UUID(str(payload.get(field))))
    except (ValueError, AttributeError) as err:
        raise error_type(f"The native {field} identity is invalid") from err


def _optional_uuid_field(
    payload: dict[object, object],
    field: str,
    error_type: type[BackendTaskError],
) -> str | None:
    value = payload.get(field)
    return None if value is None else _uuid_field(payload, field, error_type)


def _optional_text(
    payload: dict[object, object],
    field: str,
    error_type: type[InvalidStatusDataError]
    | type[BackendTaskError] = InvalidStatusDataError,
) -> str | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise error_type(f"The native {field} value is invalid")
    return value.strip() or None


def _non_negative_int(payload: dict[object, object], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise InvalidStatusDataError(f"The native {field} value is invalid")
    return value


def _bool(payload: dict[object, object], field: str) -> bool:
    value = payload.get(field)
    if not isinstance(value, bool):
        raise InvalidStatusDataError(f"The native {field} value is invalid")
    return value


def _optional_bool(
    payload: dict[object, object], field: str, error_type: type[BackendTaskError]
) -> bool | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise error_type(f"The native {field} value is invalid")
    return value


def _optional_int(
    payload: dict[object, object], field: str, error_type: type[BackendTaskError]
) -> int | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise error_type(f"The native {field} value is invalid")
    return value


def _optional_number(
    payload: dict[object, object], field: str, error_type: type[BackendTaskError]
) -> float | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, int | float) or isinstance(value, bool) or value < 0:
        raise error_type(f"The native {field} value is invalid")
    return float(value)


def _optional_datetime(
    payload: dict[object, object],
    field: str,
    error_type: type[InvalidStatusDataError]
    | type[BackendTaskError] = InvalidStatusDataError,
) -> datetime | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise error_type(f"The native {field} timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as err:
        raise error_type(f"The native {field} timestamp is invalid") from err
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise error_type(f"The native {field} timestamp needs a timezone")
    return parsed
