"""Ansible adapter tests that never start Ansible or contact a host."""

import asyncio
import json
from collections.abc import Coroutine
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from backend.homelab_backend.ansible_result import RESULT_PREFIX
from backend.homelab_backend.automation import (
    AnsibleExecutor,
    AutomationExecutionError,
    _classify_failure,
    _extract_module_payload,
    _facts_arguments,
    _inventory,
)
from backend.homelab_backend.models import (
    CustomTask,
    CustomTaskMode,
    Host,
    JobAction,
)


def _host() -> Host:
    now = datetime(2026, 1, 15, tzinfo=UTC)
    return Host(
        id=UUID("00000000-0000-4000-8000-000000000001"),
        name="Node 01",
        address="node-01.example.invalid",
        port=22,
        username="automation",
        package_provider="debian_apt",
        created_at=now,
        updated_at=now,
    )


def _task(
    *,
    mode: CustomTaskMode,
    argv: tuple[str, ...] | None,
    shell_command: str | None,
    enabled: bool = True,
) -> CustomTask:
    now = datetime(2026, 1, 15, tzinfo=UTC)
    return CustomTask(
        id=UUID("00000000-0000-4000-8000-000000000004"),
        name="Synthetic task",
        description="",
        mode=mode,
        argv=argv,
        shell_command=shell_command,
        enabled=enabled,
        created_at=now,
        updated_at=now,
    )


def _callback_output(
    result: dict[str, object], *, event: str = "ok", warning: str = ""
) -> str:
    envelope = json.dumps({"event": event, "result": result})
    return f"{warning}\n{RESULT_PREFIX}{envelope}".lstrip()


async def test_builtin_actions_dispatch_safe_ansible_modules(tmp_path: Path) -> None:
    """Connection validation covers SSH, facts/Python, and non-interactive sudo."""
    executor = AnsibleExecutor(tmp_path / "key", tmp_path / "known_hosts")
    executor._async_module = AsyncMock(  # type: ignore[method-assign]
        return_value=({}, "ok")
    )
    assert (await executor.async_execute(JobAction.TEST_CONNECTION, _host())).output
    calls = executor._async_module.await_args_list
    assert [call.args[1] for call in calls] == [
        "ansible.builtin.ping",
        "ansible.builtin.setup",
        "ansible.builtin.command",
    ]
    assert calls[0].kwargs == {"failure_code": "test_connection_failed"}
    assert calls[1].kwargs == {"failure_code": "test_connection_facts_failed"}
    assert calls[2].kwargs == {
        "become": True,
        "failure_code": "sudo_unavailable",
    }

    executor._async_module.reset_mock()
    assert (await executor.async_execute(JobAction.REBOOT, _host())).output == "ok"
    executor._async_module.assert_awaited_with(
        _host(),
        "ansible.builtin.reboot",
        become=True,
        failure_code="reboot_failed",
    )

    with pytest.raises(AutomationExecutionError, match="unsupported_action"):
        await executor.async_execute(JobAction.CUSTOM_TASK, _host())


async def test_check_and_update_normalize_snapshot_without_rebooting(
    tmp_path: Path,
) -> None:
    """Update runs APT then a read-only check and returns reboot status only."""
    executor = AnsibleExecutor(tmp_path / "key", tmp_path / "known_hosts")
    results = [
        ({}, "updated"),
        (
            {
                "ansible_facts": {
                    "ansible_distribution": "Example Linux",
                    "ansible_distribution_version": "1.0",
                    "ansible_kernel": "1.0.0-example",
                }
            },
            "facts",
        ),
        (
            {"stdout": "package-a/stable-security 2 amd64 [upgradable from: 1]"},
            "packages",
        ),
        ({"stat": {"exists": True}}, "reboot status"),
    ]
    executor._async_module = AsyncMock(side_effect=results)  # type: ignore[method-assign]

    result = await executor.async_execute(JobAction.UPDATE, _host())

    assert result.reboot_required is True
    assert result.snapshot is not None
    assert result.snapshot.updates == 1
    assert result.snapshot.security_updates == 1
    assert result.snapshot.distribution == "Example Linux"
    assert result.snapshot.checked_at.tzinfo is not None
    first_call = executor._async_module.await_args_list[0]
    assert first_call.kwargs == {
        "become": True,
        "failure_code": "update_packages_failed",
    }
    assert "ansible.builtin.apt" in str(first_call)
    assert (
        sum(
            call.args[1] == "ansible.builtin.apt"
            for call in executor._async_module.await_args_list
        )
        == 1
    )
    assert all(
        "reboot" not in str(call).split(",")[1]
        for call in executor._async_module.await_args_list[:1]
    )


async def test_check_tolerates_missing_optional_facts(tmp_path: Path) -> None:
    """Absent optional facts become None without weakening required counters."""
    executor = AnsibleExecutor(tmp_path / "key", tmp_path / "known_hosts")
    executor._async_module = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            ({}, "facts"),
            ({}, "cache"),
            ({"stdout": 123}, "packages"),
            ({}, "reboot"),
        ]
    )
    result = await executor.async_execute(JobAction.CHECK_UPDATES, _host())
    assert result.snapshot is not None
    assert result.snapshot.distribution is None
    assert result.snapshot.updates == 0
    assert not result.snapshot.reboot_required
    calls = executor._async_module.await_args_list
    assert [call.args[1] for call in calls] == [
        "ansible.builtin.setup",
        "ansible.builtin.apt",
        "ansible.builtin.command",
        "ansible.builtin.stat",
    ]
    assert calls[1].args[2] == "update_cache=true cache_valid_time=0"
    assert calls[1].kwargs == {
        "become": True,
        "failure_code": "check_updates_apt_cache_refresh_failed",
    }
    assert json.loads(calls[2].args[2])["argv"] == [
        "/usr/bin/env",
        "LC_ALL=C",
        "LANG=C",
        "/usr/bin/apt",
        "list",
        "--upgradable",
    ]
    assert calls[2].kwargs == {"failure_code": "check_updates_package_list_failed"}
    assert calls[3].kwargs == {"failure_code": "check_updates_reboot_status_failed"}


async def test_check_keeps_one_structured_result_per_sequential_phase(
    tmp_path: Path,
) -> None:
    """A whole check may log four markers while each invocation parses only one."""
    executor = AnsibleExecutor(tmp_path / "key", tmp_path / "known_hosts")
    phase_results = [
        {"ansible_facts": {"ansible_distribution": "Example Linux"}},
        {"changed": False},
        {"stdout": "Listing...\n"},
        {"stat": {"exists": False}},
    ]
    executor._async_module = AsyncMock(  # type: ignore[method-assign]
        side_effect=[(result, _callback_output(result)) for result in phase_results]
    )

    result = await executor.async_execute(JobAction.CHECK_UPDATES, _host())

    assert result.output.count(RESULT_PREFIX) == 4
    assert result.snapshot is not None
    assert result.snapshot.updates == 0


async def test_custom_task_modes_and_disabled_state(tmp_path: Path) -> None:
    """Command and shell modes remain visibly separate at execution."""
    executor = AnsibleExecutor(tmp_path / "key", tmp_path / "known_hosts")
    executor._async_module = AsyncMock(return_value=({}, "done"))  # type: ignore[method-assign]
    command = _task(mode=CustomTaskMode.COMMAND, argv=("uptime",), shell_command=None)
    shell = _task(mode=CustomTaskMode.SHELL, argv=None, shell_command="printf ok")
    assert (await executor.async_execute_custom(command, _host())).output == "done"
    assert "ansible.builtin.command" in str(executor._async_module.await_args)
    assert (await executor.async_execute_custom(shell, _host())).output == "done"
    assert "ansible.builtin.shell" in str(executor._async_module.await_args)

    with pytest.raises(AutomationExecutionError, match="custom_task_disabled"):
        await executor.async_execute_custom(
            _task(
                mode=CustomTaskMode.COMMAND,
                argv=("true",),
                shell_command=None,
                enabled=False,
            ),
            _host(),
        )
    with pytest.raises(AutomationExecutionError, match="invalid_custom_task"):
        await executor.async_execute_custom(
            _task(mode=CustomTaskMode.COMMAND, argv=None, shell_command=None),
            _host(),
        )


@pytest.mark.parametrize(
    "output",
    [
        "no marker",
        f"{RESULT_PREFIX}{{invalid}}",
        _callback_output({}, event="failed"),
        f'{RESULT_PREFIX}{{"event":"ok","result":[]}}',
    ],
)
def test_ansible_output_parser_rejects_unstructured_output(output: str) -> None:
    """Unexpected callback formats fail closed with a safe error category."""
    with pytest.raises(AutomationExecutionError, match="invalid_ansible_output"):
        _extract_module_payload(output)


def test_ansible_output_parser_rejects_ambiguous_multiple_results() -> None:
    """Exactly one callback result is required for the isolated one-host run."""
    output = f"{_callback_output({})}\n{_callback_output({})}"
    with pytest.raises(AutomationExecutionError, match="invalid_ansible_output"):
        _extract_module_payload(output)


def test_ansible_output_parser_extracts_object() -> None:
    assert _extract_module_payload(
        _callback_output(
            {"changed": False},
            warning="[WARNING]: Synthetic interpreter discovery warning",
        )
    ) == {"changed": False}


def test_ansible_output_parser_rejects_non_object_decoder_result() -> None:
    """The normalized Ansible payload must remain an object."""
    with (
        patch("backend.homelab_backend.automation.json.loads", return_value=[]),
        pytest.raises(AutomationExecutionError, match="invalid_ansible_output"),
    ):
        _extract_module_payload(_callback_output({}))


class FakeProcess:
    """Minimal asyncio subprocess double."""

    def __init__(
        self,
        *,
        returncode: int = 0,
        output: bytes = (b'HOMELAB_UPDATES_RESULT={"event":"ok","result":{"ok":true}}'),
    ) -> None:
        self.returncode = returncode
        self.output = output
        self.killed = False
        self.waited = False

    async def communicate(self) -> tuple[bytes, None]:
        return self.output, None

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        self.waited = True
        return self.returncode


async def test_module_runner_uses_exec_inventory_and_become(tmp_path: Path) -> None:
    """The adapter passes an argv vector and never invokes a shell."""
    process = FakeProcess()
    executor = AnsibleExecutor(tmp_path / "key", tmp_path / "known_hosts")
    with patch(
        "asyncio.create_subprocess_exec", AsyncMock(return_value=process)
    ) as spawn:
        payload, output = await executor._async_module(
            _host(), "ansible.builtin.ping", "data=synthetic", become=True
        )
    assert payload == {"ok": True}
    assert "SUCCESS" not in output
    args = spawn.await_args.args
    assert args[0] == "ansible"
    assert "--become" in args
    assert "--module-name" in args
    assert spawn.await_args.kwargs["stderr"] is asyncio.subprocess.STDOUT
    environment = spawn.await_args.kwargs["env"]
    assert environment["ANSIBLE_STDOUT_CALLBACK"] == "homelab_json"
    assert environment["ANSIBLE_LOAD_CALLBACK_PLUGINS"] == "True"
    assert environment["ANSIBLE_NOCOLOR"] == "True"
    assert Path(environment["ANSIBLE_LOCAL_TEMP"]).name == "ansible-local"


async def test_module_runner_maps_failure_and_timeout(tmp_path: Path) -> None:
    executor = AnsibleExecutor(tmp_path / "key", tmp_path / "known_hosts")
    failed = FakeProcess(returncode=2, output=b"synthetic failure")
    with (
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=failed)),
        pytest.raises(AutomationExecutionError, match="ansible_failed"),
    ):
        await executor._async_module(_host(), "ansible.builtin.ping")

    timed_out = FakeProcess()

    async def timeout(
        awaitable: Coroutine[object, object, object], **kwargs: float
    ) -> object:
        assert kwargs == {"timeout": 3600}
        awaitable.close()
        raise TimeoutError

    with (
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=timed_out)),
        patch("asyncio.wait_for", timeout),
        pytest.raises(AutomationExecutionError, match="execution_timeout"),
    ):
        await executor._async_module(_host(), "ansible.builtin.ping")
    assert timed_out.killed
    assert timed_out.waited


async def test_module_runner_ignores_warnings_when_result_and_exit_are_successful(
    tmp_path: Path,
) -> None:
    """Interpreter and APT warnings remain logs, never failure signals."""
    output = _callback_output(
        {"stdout": "Listing...\n"},
        warning=(
            "[WARNING]: Synthetic interpreter discovery warning\n"
            "WARNING: apt does not have a stable CLI interface"
        ),
    ).encode()
    executor = AnsibleExecutor(tmp_path / "key", tmp_path / "known_hosts")
    with patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=FakeProcess(output=output)),
    ):
        payload, log = await executor._async_module(_host(), "ansible.builtin.command")
    assert payload["stdout"] == "Listing...\n"
    assert "interpreter discovery warning" in log


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("No python interpreters found for host", "python_interpreter_unavailable"),
        ("/bin/sh: python3: not found", "python_interpreter_unavailable"),
        (
            "Failed to find a suitable Python interpreter",
            "python_interpreter_unavailable",
        ),
        ("Missing sudo password", "sudo_unavailable"),
        ("sudo: not found", "sudo_unavailable"),
        ("Could not get lock /var/lib/dpkg/lock", "apt_lock_unavailable"),
        ("Synthetic task failure", "check_updates_package_list_failed"),
    ],
)
def test_ansible_failures_receive_safe_specific_codes(
    output: str, expected: str
) -> None:
    assert _classify_failure("check_updates_package_list_failed", output) == expected


async def test_module_runner_rejects_invalid_structured_success(tmp_path: Path) -> None:
    """Exit zero without one valid callback envelope fails closed."""
    executor = AnsibleExecutor(tmp_path / "key", tmp_path / "known_hosts")
    with (
        patch(
            "asyncio.create_subprocess_exec",
            AsyncMock(return_value=FakeProcess(output=b"unstructured success")),
        ),
        pytest.raises(AutomationExecutionError, match="invalid_ansible_output"),
    ):
        await executor._async_module(_host(), "ansible.builtin.command")


async def test_module_runner_preserves_phase_for_real_task_failure(
    tmp_path: Path,
) -> None:
    """A nonzero Ansible task result remains a phase-specific backend failure."""
    executor = AnsibleExecutor(tmp_path / "key", tmp_path / "known_hosts")
    output = _callback_output(
        {"failed": True, "msg": "Synthetic package-list failure"}, event="failed"
    ).encode()
    with (
        patch(
            "asyncio.create_subprocess_exec",
            AsyncMock(return_value=FakeProcess(returncode=2, output=output)),
        ),
        pytest.raises(
            AutomationExecutionError,
            match="check_updates_package_list_failed",
        ),
    ):
        await executor._async_module(
            _host(),
            "ansible.builtin.command",
            failure_code="check_updates_package_list_failed",
        )


def test_inventory_uses_silent_discovery_without_python_path_assumptions(
    tmp_path: Path,
) -> None:
    """Every module uses auto_silent; /usr/bin/python is never assumed."""
    inventory = _inventory(_host(), tmp_path / "known_hosts")
    host_values = inventory["all"]["hosts"][str(_host().id)]  # type: ignore[index]
    assert host_values["ansible_python_interpreter"] == "auto_silent"
    assert "/usr/bin/python" not in json.dumps(inventory)


def test_debian_python3_discovery_is_consistent_without_python_symlink(
    tmp_path: Path,
) -> None:
    """All actions rediscover Python consistently instead of assuming `python`."""
    inventory = _inventory(_host(), tmp_path / "known_hosts")
    serialized = json.dumps(inventory)
    synthetic_facts = {
        "ansible_facts": {
            "ansible_distribution": "Debian",
            "ansible_python": {
                "executable": "/usr/bin/python3",
                "version": {"major": 3},
            },
            "discovered_interpreter_python": "/usr/bin/python3",
        }
    }
    assert "auto_silent" in serialized
    assert "ansible_python_interpreter" in serialized
    assert synthetic_facts["ansible_facts"]["discovered_interpreter_python"] == (
        "/usr/bin/python3"
    )
    assert '"/usr/bin/python"' not in serialized


def test_fact_filter_covers_distribution_kernel_and_python() -> None:
    arguments = json.loads(_facts_arguments())
    assert arguments["filter"] == [
        "ansible_distribution*",
        "ansible_kernel",
        "ansible_python*",
        "discovered_interpreter_python",
    ]
