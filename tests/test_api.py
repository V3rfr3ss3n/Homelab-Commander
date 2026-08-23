"""Contract and parser tests for external HTTP adapters."""

from datetime import UTC

import pytest
from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectionError

from custom_components.homelab_updates.api import (
    NativeBackendClient,
    SemaphoreClient,
    StatusClient,
    normalize_url,
    parse_hosts,
    parse_task,
)
from custom_components.homelab_updates.domain import Command, TaskPhase
from custom_components.homelab_updates.exceptions import (
    AuthenticationError,
    BackendTaskError,
    CannotConnectError,
    InvalidProjectError,
    InvalidStatusDataError,
    InvalidUrlError,
    SemaphoreTaskError,
)

from .conftest import API_TOKEN, SEMAPHORE_URL, STATUS_URL

NATIVE_URL = "https://backend.example.invalid"
HOST_ID = "00000000-0000-4000-8000-000000000001"
JOB_ID = "00000000-0000-4000-8000-000000000002"


def _native_client(session: ClientSession) -> NativeBackendClient:
    return NativeBackendClient(session, NATIVE_URL, API_TOKEN)


def _native_host_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": HOST_ID,
        "name": "Node 01",
        "distribution": "Example Linux",
        "distribution_version": "1.0",
        "kernel": "1.0.0-example",
        "updates": 3,
        "security_updates": 1,
        "reboot_required": False,
        "status": "ok",
        "checked_at": "2026-01-15T12:00:00Z",
    }
    payload.update(overrides)
    return payload


def _native_job_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": JOB_ID,
        "action": "update",
        "host_id": HOST_ID,
        "state": "queued",
        "created_at": "2026-01-15T12:00:00Z",
        "finished_at": None,
        "error_code": None,
        "reboot_required": None,
    }
    payload.update(overrides)
    return payload


def _payload(**overrides: object) -> dict[str, object]:
    host: dict[str, object] = {
        "checked_at": "2026-01-15T12:00:00Z",
        "distribution": "Example Linux",
        "distribution_version": "1.0",
        "host": "node-01",
        "hostname": "example-node",
        "kernel": "1.0.0-generic",
        "reboot_required": False,
        "security_updates": 2,
        "status": "critical",
        "updates": 5,
    }
    host.update(overrides)
    return {"node-01": host}


@pytest.mark.parametrize(
    ("value", "base", "expected"),
    [
        (" https://service.example.invalid/ ", True, "https://service.example.invalid"),
        (
            "http://service.example.invalid/api/",
            True,
            "http://service.example.invalid/api",
        ),
        (
            "https://service.example.invalid/status",
            False,
            "https://service.example.invalid/status",
        ),
    ],
)
def test_normalize_url(value: str, base: bool, expected: str) -> None:
    """Safe HTTP URLs are normalized predictably."""
    assert normalize_url(value, base=base) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "ftp://service.example.invalid",
        "https://user:secret@service.example.invalid",
        "https://service.example.invalid/#fragment",
        "https://service.example.invalid/?query=not-allowed-for-base",
        "https://service.example.invalid/status?query=not-allowed",
        "https://[invalid",
    ],
)
def test_normalize_url_rejects_unsafe_base(value: str) -> None:
    """Unsafe base URLs never reach an HTTP request."""
    with pytest.raises(InvalidUrlError):
        normalize_url(value, base=True)


def test_parse_hosts_valid() -> None:
    """A valid response becomes a typed immutable snapshot."""
    host = parse_hosts(_payload())["node-01"]
    assert host.display_name == "example-node"
    assert host.distribution_display == "Example Linux 1.0"
    assert host.updates == 5
    assert host.security_updates == 2
    assert host.checked_at.tzinfo is UTC


def test_parse_hosts_empty() -> None:
    """An empty but valid snapshot is supported."""
    assert parse_hosts({}) == {}


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"": {}},
        {"node-01": []},
        _payload(host="different-node"),
        _payload(updates=True),
        _payload(updates=-1),
        _payload(security_updates="not-a-number"),
        _payload(reboot_required="perhaps"),
        _payload(checked_at="2026-01-15T12:00:00"),
        _payload(checked_at="invalid"),
        _payload(hostname=42),
        _payload(checked_at=None),
        _payload(updates=1.5),
    ],
)
def test_parse_hosts_rejects_invalid_data(payload: object) -> None:
    """Invalid host fields fail the complete atomic snapshot."""
    with pytest.raises(InvalidStatusDataError):
        parse_hosts(payload)


@pytest.mark.parametrize(
    ("updates", "reboot_required", "expected_updates", "expected_reboot"),
    [
        ("5", "true", 5, True),
        (5.0, 1, 5, True),
        (0, "off", 0, False),
    ],
)
def test_parse_hosts_compatible_scalars(
    updates: object,
    reboot_required: object,
    expected_updates: int,
    expected_reboot: bool,
) -> None:
    """Documented integer and boolean compatible values are normalized."""
    host = parse_hosts(_payload(updates=updates, reboot_required=reboot_required))[
        "node-01"
    ]
    assert host.updates == expected_updates
    assert host.reboot_required is expected_reboot


def test_parse_hosts_optional_fields() -> None:
    """Absent optional descriptive fields remain None."""
    host = parse_hosts(
        _payload(
            hostname=None,
            distribution=None,
            distribution_version=None,
            kernel=None,
            status=None,
        )
    )["node-01"]
    assert host.display_name == "node-01"
    assert host.distribution_display is None


@pytest.mark.parametrize(
    ("status", "phase"),
    [
        ("waiting", TaskPhase.WAITING),
        ("queued", TaskPhase.WAITING),
        ("running", TaskPhase.RUNNING),
        ("success", TaskPhase.SUCCESS),
        ("failed", TaskPhase.FAILED),
        ("future-state", TaskPhase.UNKNOWN),
    ],
)
def test_parse_task_states(status: str, phase: TaskPhase) -> None:
    """Known and future task states normalize without crashes."""
    assert parse_task({"id": 123, "status": status}).phase is phase


@pytest.mark.parametrize(
    "payload", [[], {}, {"id": True}, {"id": 0}, {"id": 1, "status": 4}]
)
def test_parse_task_rejects_invalid_payload(payload: object) -> None:
    """Malformed task responses are safe errors."""
    with pytest.raises(SemaphoreTaskError):
        parse_task(payload)


def test_parse_task_alternate_id_and_default_state() -> None:
    """Semaphore response aliases and absent start state are supported."""
    task = parse_task({"task_id": 7})
    assert task.task_id == 7
    assert task.phase is TaskPhase.WAITING


async def test_status_client_fetches_once(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
) -> None:
    """The status adapter performs one request and returns normalized hosts."""
    aioclient_mock.get(STATUS_URL, json=_payload())  # type: ignore[attr-defined]
    client = StatusClient(aiohttp_client_session, STATUS_URL)

    hosts = await client.async_get_hosts()

    assert hosts["node-01"].updates == 5
    assert aioclient_mock.call_count == 1  # type: ignore[attr-defined]


async def test_status_client_invalid_json(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
) -> None:
    """A non-JSON response is classified as invalid status data."""
    aioclient_mock.get(STATUS_URL, text="not json")  # type: ignore[attr-defined]
    with pytest.raises(InvalidStatusDataError):
        await StatusClient(aiohttp_client_session, STATUS_URL).async_validate()


async def test_status_client_http_error(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
) -> None:
    """A failed endpoint is a retryable connection error."""
    aioclient_mock.get(STATUS_URL, status=503)  # type: ignore[attr-defined]
    with pytest.raises(CannotConnectError):
        await StatusClient(aiohttp_client_session, STATUS_URL).async_get_hosts()


async def test_status_client_transport_error(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
) -> None:
    """Transport exceptions are translated without endpoint details."""
    aioclient_mock.get(STATUS_URL, exc=ClientConnectionError())  # type: ignore[attr-defined]
    with pytest.raises(CannotConnectError):
        await StatusClient(aiohttp_client_session, STATUS_URL).async_get_hosts()


async def test_status_client_rejects_large_response(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
) -> None:
    """Oversized status documents are rejected before parsing."""
    aioclient_mock.get(STATUS_URL, content=b"x" * (2 * 1024 * 1024 + 1))  # type: ignore[attr-defined]
    with pytest.raises(InvalidStatusDataError):
        await StatusClient(aiohttp_client_session, STATUS_URL).async_get_hosts()


def _semaphore_client(session: ClientSession) -> SemaphoreClient:
    return SemaphoreClient(
        session,
        SEMAPHORE_URL,
        API_TOKEN,
        1,
        {
            Command.CHECK_ALL: 11,
            Command.UPDATE_HOST: 12,
            Command.REBOOT_HOST: 13,
            Command.REFRESH_STATUS: 14,
        },
    )


async def test_semaphore_validate_and_auth_header(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
) -> None:
    """Project validation sends a Bearer token without a query secret."""
    url = f"{SEMAPHORE_URL}/api/project/1"
    aioclient_mock.get(url, json={"id": 1})  # type: ignore[attr-defined]

    await _semaphore_client(aiohttp_client_session).async_validate()

    assert aioclient_mock.call_count == 1  # type: ignore[attr-defined]
    assert (  # type: ignore[attr-defined]
        aioclient_mock.mock_calls[0][3]["Authorization"] == f"Bearer {API_TOKEN}"
    )


@pytest.mark.parametrize(
    ("command", "host_id", "template_id"),
    [
        (Command.CHECK_ALL, None, 11),
        (Command.UPDATE_HOST, "node-01", 12),
        (Command.REBOOT_HOST, "node-01", 13),
        (Command.REFRESH_STATUS, None, 14),
    ],
)
async def test_start_command_payload(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
    command: Command,
    host_id: str | None,
    template_id: int,
) -> None:
    """Commands choose the configured template and only host actions use limit."""
    url = f"{SEMAPHORE_URL}/api/project/1/tasks"
    aioclient_mock.post(url, json={"id": 123})  # type: ignore[attr-defined]

    task = await _semaphore_client(aiohttp_client_session).async_start_command(
        command, host_id
    )

    sent = aioclient_mock.mock_calls[0][2]  # type: ignore[attr-defined]
    assert sent["template_id"] == template_id
    assert sent.get("limit") == host_id
    assert task.task_id == 123


async def test_start_host_command_requires_host(
    aiohttp_client_session: ClientSession,
) -> None:
    """A host command without a target is rejected before network I/O."""
    with pytest.raises(SemaphoreTaskError):
        await _semaphore_client(aiohttp_client_session).async_start_command(
            Command.UPDATE_HOST
        )


async def test_unconfigured_command_is_rejected(
    aiohttp_client_session: ClientSession,
) -> None:
    """Missing command capability fails before a backend request."""
    client = SemaphoreClient(
        aiohttp_client_session,
        SEMAPHORE_URL,
        API_TOKEN,
        1,
        {},
    )
    with pytest.raises(SemaphoreTaskError):
        await client.async_start_command(Command.CHECK_ALL)


async def test_auxiliary_semaphore_endpoints(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
) -> None:
    """Templates, generic tasks, task state, and output use project-scoped paths."""
    client = _semaphore_client(aiohttp_client_session)
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{SEMAPHORE_URL}/api/project/1/templates", json=[{"id": 11}]
    )
    assert await client.async_get_templates() == [{"id": 11}]

    task_url = f"{SEMAPHORE_URL}/api/project/1/tasks"
    aioclient_mock.post(task_url, json={"id": 501})  # type: ignore[attr-defined]
    assert (await client.async_start_task(99, "node-01")).task_id == 501
    assert aioclient_mock.mock_calls[-1][2] == {  # type: ignore[attr-defined]
        "template_id": 99,
        "limit": "node-01",
    }

    aioclient_mock.post(task_url, json={"id": 502})  # type: ignore[attr-defined]
    await client.async_start_task(100)
    assert aioclient_mock.mock_calls[-1][2] == {"template_id": 100}  # type: ignore[attr-defined]

    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{task_url}/501", json={"id": 501, "status": "running"}
    )
    assert (await client.async_get_task(501)).phase is TaskPhase.RUNNING
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{task_url}/501/output", json=[{"output": "synthetic"}]
    )
    assert await client.async_get_task_output(501) == [{"output": "synthetic"}]

    aioclient_mock.get(  # type: ignore[attr-defined]
        task_url,
        json=[
            {"id": 501, "status": "success"},
            {"id": 502, "status": "running"},
        ],
    )
    tasks = await client.async_get_tasks()
    assert [task.task_id for task in tasks] == [501, 502]


async def test_semaphore_custom_task_is_fail_closed(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
) -> None:
    """Custom legacy templates always carry an explicit inventory limit."""
    task_url = f"{SEMAPHORE_URL}/api/project/1/tasks"
    aioclient_mock.post(task_url, json={"id": 503})  # type: ignore[attr-defined]
    client = _semaphore_client(aiohttp_client_session)

    task = await client.async_run_task("99", "node-01")

    assert task.task_id == 503
    assert aioclient_mock.mock_calls[-1][2] == {  # type: ignore[attr-defined]
        "template_id": 99,
        "limit": "node-01",
    }
    with pytest.raises(SemaphoreTaskError):
        await client.async_run_task("99", " ")
    with pytest.raises(SemaphoreTaskError):
        await client.async_run_task("not-a-number", "node-01")


async def test_semaphore_transport_error(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
) -> None:
    """Backend transport exceptions are stable connection errors."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{SEMAPHORE_URL}/api/project/1", exc=ClientConnectionError()
    )
    with pytest.raises(CannotConnectError):
        await _semaphore_client(aiohttp_client_session).async_validate()


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, AuthenticationError),
        (403, AuthenticationError),
        (404, InvalidProjectError),
        (500, CannotConnectError),
    ],
)
async def test_semaphore_validation_errors(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
    status: int,
    error: type[Exception],
) -> None:
    """HTTP failures map to stable safe exception categories."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{SEMAPHORE_URL}/api/project/1", status=status
    )
    with pytest.raises(error):
        await _semaphore_client(aiohttp_client_session).async_validate()


async def test_native_client_validates_and_parses_hosts(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
) -> None:
    """The native provider normalizes UUID hosts and accepts never-checked hosts."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/info", json={"api_version": "v1"}
    )
    client = _native_client(aiohttp_client_session)
    await client.async_validate()

    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/hosts",
        json=[_native_host_payload(checked_at=None)],
    )
    hosts = await client.async_get_hosts()
    assert hosts[HOST_ID].hostname == "Node 01"
    assert hosts[HOST_ID].checked_at is None


async def test_native_client_actions_and_batch_tracking(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
) -> None:
    """Global and host actions keep their exact native job identities."""
    client = _native_client(aiohttp_client_session)
    aioclient_mock.post(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/hosts/{HOST_ID}/actions/update",
        json=_native_job_payload(),
    )
    assert (await client.async_update_host(HOST_ID)).task_id == JOB_ID

    second_job = "00000000-0000-4000-8000-000000000003"
    aioclient_mock.post(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/actions/check",
        json=[
            _native_job_payload(action="check_updates"),
            _native_job_payload(id=second_job, action="check_updates", state="running"),
        ],
    )
    batch = await client.async_check_hosts()
    assert batch.phase is TaskPhase.RUNNING

    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/jobs/{JOB_ID}",
        json=_native_job_payload(state="success"),
    )
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/jobs/{second_job}",
        json=_native_job_payload(id=second_job, state="success"),
    )
    completed = await client.async_get_task(batch.task_id)
    assert completed.phase is TaskPhase.SUCCESS


async def test_native_client_lists_jobs_and_rejects_invalid_target(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
) -> None:
    """Job history is typed and malformed mutation targets never reach HTTP."""
    client = _native_client(aiohttp_client_session)
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/jobs",
        json=[
            _native_job_payload(
                state="failed",
                host_name="Node 01",
                started_at="2026-01-15T12:00:01Z",
                finished_at="2026-01-15T12:00:03Z",
                exit_code=2,
                error_code="synthetic",
                short_error="Synthetic failure",
                duration=2.0,
                log_available=True,
            )
        ],
    )
    tasks = await client.async_get_tasks()
    assert tasks[0].phase is TaskPhase.FAILED
    assert tasks[0].error_code == "synthetic"
    assert tasks[0].host_name == "Node 01"
    assert tasks[0].exit_code == 2
    assert tasks[0].duration == 2.0
    assert tasks[0].log_available
    assert tasks[0].job_url == f"{NATIVE_URL}/#/jobs/{JOB_ID}"
    with pytest.raises(BackendTaskError):
        await client.async_reboot_host("not-a-uuid")


async def test_native_client_gets_job_log_and_maps_not_found(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
) -> None:
    """Job logs are explicit, typed, and never put the API token in the URL."""
    client = _native_client(aiohttp_client_session)
    url = f"{NATIVE_URL}/api/v1/jobs/{JOB_ID}/log"
    aioclient_mock.get(  # type: ignore[attr-defined]
        url,
        json={"job_id": JOB_ID, "output": "redacted output", "truncated": False},
    )

    log = await client.async_get_job_log(JOB_ID)

    assert log.output == "redacted output"
    assert API_TOKEN not in str(aioclient_mock.mock_calls[-1][0])  # type: ignore[attr-defined]

    aioclient_mock.clear_requests()  # type: ignore[attr-defined]
    aioclient_mock.get(url, status=404)  # type: ignore[attr-defined]
    with pytest.raises(BackendTaskError, match="Job log not found"):
        await client.async_get_job_log(JOB_ID)


async def test_native_client_discovers_and_runs_custom_tasks(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
) -> None:
    """Custom task metadata stays provider-neutral and execution is host-limited."""
    task_id = "00000000-0000-4000-8000-000000000004"
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/custom-tasks",
        json=[
            {
                "id": task_id,
                "name": "Synthetic task",
                "description": "No real command",
                "enabled": True,
                "mode": "command",
                "argv": ["true"],
            }
        ],
    )
    client = _native_client(aiohttp_client_session)
    tasks = await client.async_get_custom_tasks()
    assert tasks[0].task_id == task_id
    assert tasks[0].name == "Synthetic task"

    aioclient_mock.post(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/hosts/{HOST_ID}/actions/tasks/{task_id}",
        json=_native_job_payload(action="custom_task"),
    )
    assert (await client.async_run_task(task_id, HOST_ID)).task_id == JOB_ID


@pytest.mark.parametrize("status", [401, 403])
async def test_native_client_authentication_errors(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
    status: int,
) -> None:
    """Native authentication failures use the common reauth category."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/info", status=status
    )
    with pytest.raises(AuthenticationError):
        await _native_client(aiohttp_client_session).async_validate()


async def test_native_client_rejects_incompatible_and_non_list_responses(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
) -> None:
    """Every native collection and compatibility boundary fails closed."""
    client = _native_client(aiohttp_client_session)
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/info", json={"api_version": "v2"}
    )
    with pytest.raises(InvalidStatusDataError):
        await client.async_validate()

    for path in ("hosts", "jobs", "custom-tasks"):
        aioclient_mock.get(  # type: ignore[attr-defined]
            f"{NATIVE_URL}/api/v1/{path}", json={"unexpected": True}
        )
    with pytest.raises(InvalidStatusDataError):
        await client.async_get_hosts()
    with pytest.raises(BackendTaskError):
        await client.async_get_tasks()
    with pytest.raises(BackendTaskError):
        await client.async_get_custom_tasks()

    aioclient_mock.post(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/actions/check", json={"unexpected": True}
    )
    with pytest.raises(BackendTaskError):
        await client.async_refresh_hosts()


async def test_native_client_duplicate_hosts_and_empty_batch(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
) -> None:
    """Duplicate UUIDs are rejected and an empty batch is already complete."""
    client = _native_client(aiohttp_client_session)
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/hosts",
        json=[_native_host_payload(), _native_host_payload(name="Duplicate")],
    )
    with pytest.raises(InvalidStatusDataError):
        await client.async_get_hosts()
    assert (await client.async_get_task("batch:")).phase is TaskPhase.SUCCESS


@pytest.mark.parametrize(
    "payload",
    [
        [],
        _native_host_payload(id="invalid"),
        _native_host_payload(name=1),
        _native_host_payload(updates=-1),
        _native_host_payload(updates=True),
        _native_host_payload(reboot_required="false"),
        _native_host_payload(checked_at=1),
        _native_host_payload(checked_at="invalid"),
        _native_host_payload(checked_at="2026-01-15T12:00:00"),
    ],
)
async def test_native_client_rejects_invalid_host_fields(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
    payload: object,
) -> None:
    """Malformed host fields never become partial Home Assistant state."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/hosts", json=[payload]
    )
    with pytest.raises(InvalidStatusDataError):
        await _native_client(aiohttp_client_session).async_get_hosts()


@pytest.mark.parametrize(
    "payload",
    [
        [],
        _native_job_payload(id="invalid"),
        _native_job_payload(state=1),
        _native_job_payload(host_id="invalid"),
        _native_job_payload(action=1),
        _native_job_payload(created_at=1),
        _native_job_payload(created_at="invalid"),
        _native_job_payload(created_at="2026-01-15T12:00:00"),
        _native_job_payload(reboot_required="false"),
        _native_job_payload(host_name=1),
        _native_job_payload(started_at="invalid"),
        _native_job_payload(exit_code=True),
        _native_job_payload(short_error=1),
        _native_job_payload(duration=-1),
        _native_job_payload(log_available="true"),
    ],
)
async def test_native_client_rejects_invalid_job_fields(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
    payload: object,
) -> None:
    """Malformed job metadata maps to one safe task error."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/jobs", json=[payload]
    )
    with pytest.raises(BackendTaskError):
        await _native_client(aiohttp_client_session).async_get_tasks()


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"id": JOB_ID, "name": "Task", "enabled": "yes"},
        {"id": JOB_ID, "name": 1, "enabled": True},
    ],
)
async def test_native_client_rejects_invalid_custom_tasks(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
    payload: object,
) -> None:
    """Dynamic task discovery accepts only valid provider-neutral metadata."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/custom-tasks", json=[payload]
    )
    with pytest.raises(BackendTaskError):
        await _native_client(aiohttp_client_session).async_get_custom_tasks()


async def test_native_client_rejects_http_and_payload_failures(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
) -> None:
    """HTTP, JSON, and response-size failures expose no backend body."""
    client = _native_client(aiohttp_client_session)
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/info", status=500, content=b"sensitive body"
    )
    with pytest.raises(CannotConnectError):
        await client.async_validate()
    aioclient_mock.clear_requests()  # type: ignore[attr-defined]

    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/info", content=b"not-json"
    )
    with pytest.raises(InvalidStatusDataError):
        await client.async_validate()
    aioclient_mock.clear_requests()  # type: ignore[attr-defined]

    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/info", content=b"0" * (2 * 1024 * 1024 + 1)
    )
    with pytest.raises(InvalidStatusDataError):
        await client.async_validate()


async def test_native_client_covers_single_jobs_and_all_batch_phases(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
) -> None:
    """Single-job lookup and empty, waiting, and failed batches are stable."""
    client = _native_client(aiohttp_client_session)
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/jobs/{JOB_ID}",
        json=_native_job_payload(reboot_required=True),
    )
    assert (await client.async_get_task(JOB_ID)).reboot_required is True

    for payload, phase in (
        ([], TaskPhase.SUCCESS),
        ([_native_job_payload()], TaskPhase.WAITING),
        ([_native_job_payload(state="failed")], TaskPhase.FAILED),
    ):
        aioclient_mock.post(  # type: ignore[attr-defined]
            f"{NATIVE_URL}/api/v1/actions/check", json=payload
        )
        assert (await client.async_check_hosts()).phase is phase
        aioclient_mock.clear_requests()  # type: ignore[attr-defined]


async def test_native_client_maps_connection_errors(
    aioclient_mock: object,
    aiohttp_client_session: ClientSession,
) -> None:
    """Transport exceptions map to the provider-neutral connection error."""
    aioclient_mock.get(  # type: ignore[attr-defined]
        f"{NATIVE_URL}/api/v1/info", exc=ClientConnectionError()
    )
    with pytest.raises(CannotConnectError):
        await _native_client(aiohttp_client_session).async_validate()
