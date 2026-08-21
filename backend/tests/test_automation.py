"""Ansible adapter tests that never start Ansible or contact a host."""

import asyncio
from collections.abc import Coroutine
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from backend.homelab_backend.automation import (
    AnsibleExecutor,
    AutomationExecutionError,
    _extract_module_payload,
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


async def test_builtin_actions_dispatch_safe_ansible_modules(tmp_path: Path) -> None:
    """Built-ins select exact modules and only privileged actions use become."""
    executor = AnsibleExecutor(tmp_path / "key", tmp_path / "known_hosts")
    executor._async_module = AsyncMock(  # type: ignore[method-assign]
        return_value=({}, "ok")
    )
    assert (
        await executor.async_execute(JobAction.TEST_CONNECTION, _host())
    ).output == "ok"
    executor._async_module.assert_awaited_with(_host(), "ansible.builtin.ping")

    executor._async_module.reset_mock()
    assert (await executor.async_execute(JobAction.REBOOT, _host())).output == "ok"
    executor._async_module.assert_awaited_with(
        _host(), "ansible.builtin.reboot", become=True
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
    assert first_call.kwargs == {"become": True}
    assert "ansible.builtin.apt" in str(first_call)
    assert all(
        "reboot" not in str(call).split(",")[1]
        for call in executor._async_module.await_args_list[:1]
    )


async def test_check_tolerates_missing_optional_facts(tmp_path: Path) -> None:
    """Absent optional facts become None without weakening required counters."""
    executor = AnsibleExecutor(tmp_path / "key", tmp_path / "known_hosts")
    executor._async_module = AsyncMock(  # type: ignore[method-assign]
        side_effect=[({}, "facts"), ({"stdout": 123}, "packages"), ({}, "reboot")]
    )
    result = await executor.async_execute(JobAction.CHECK_UPDATES, _host())
    assert result.snapshot is not None
    assert result.snapshot.distribution is None
    assert result.snapshot.updates == 0
    assert not result.snapshot.reboot_required


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
    ["no json", "host | SUCCESS => {invalid}", 'host | SUCCESS => ["list"]'],
)
def test_ansible_output_parser_rejects_unstructured_output(output: str) -> None:
    """Unexpected callback formats fail closed with a safe error category."""
    with pytest.raises(AutomationExecutionError, match="invalid_ansible_output"):
        _extract_module_payload(output)


def test_ansible_output_parser_extracts_object() -> None:
    assert _extract_module_payload('host | SUCCESS => {"changed": false}') == {
        "changed": False
    }


def test_ansible_output_parser_rejects_non_object_decoder_result() -> None:
    """The normalized Ansible payload must remain an object."""
    with (
        patch("backend.homelab_backend.automation.json.loads", return_value=[]),
        pytest.raises(AutomationExecutionError, match="invalid_ansible_output"),
    ):
        _extract_module_payload("{}")


class FakeProcess:
    """Minimal asyncio subprocess double."""

    def __init__(
        self, *, returncode: int = 0, output: bytes = b'host => {"ok": true}'
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
