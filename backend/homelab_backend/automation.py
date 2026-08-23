"""Safe asynchronous Ansible execution adapter."""

import asyncio
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .ansible_result import RESULT_PREFIX
from .models import CustomTask, CustomTaskMode, Host, JobAction
from .package_providers import package_provider


@dataclass(frozen=True, slots=True)
class HostSnapshot:
    """Normalized status collected by an execution adapter."""

    distribution: str | None
    distribution_version: str | None
    kernel: str | None
    updates: int
    security_updates: int
    reboot_required: bool
    status: str
    checked_at: datetime


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Bounded executor result consumed by the job service."""

    output: str
    snapshot: HostSnapshot | None = None
    reboot_required: bool | None = None
    exit_code: int = 0


class AutomationExecutor(Protocol):
    """Execute one built-in operation for exactly one host."""

    async def async_execute(self, action: JobAction, host: Host) -> ExecutionResult:
        """Run the operation without blocking the event loop."""

    async def async_execute_custom(
        self, task: CustomTask, host: Host
    ) -> ExecutionResult:
        """Run one validated custom task for exactly one host."""


class AutomationExecutionError(Exception):
    """Safe execution failure with bounded diagnostic output."""

    def __init__(self, code: str, output: str, *, exit_code: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.output = output
        self.exit_code = exit_code


class AnsibleExecutor:
    """Run built-in Ansible modules with generated single-host inventory."""

    def __init__(
        self,
        private_key_path: Path,
        known_hosts_path: Path,
        *,
        command_timeout: float = 3600,
    ) -> None:
        self._private_key_path = private_key_path
        self._known_hosts_path = known_hosts_path
        self._command_timeout = command_timeout

    async def async_execute(self, action: JobAction, host: Host) -> ExecutionResult:
        """Execute a built-in action; reboot is never inferred from update."""
        if action is JobAction.TEST_CONNECTION:
            return await self._async_test_connection(host)
        if action is JobAction.CHECK_UPDATES:
            return await self._async_check(host)
        if action is JobAction.UPDATE:
            provider = package_provider(host.package_provider)
            module, arguments = provider.update_module
            _, update_output = await self._async_module(
                host,
                module,
                arguments,
                become=True,
                failure_code="update_packages_failed",
            )
            check = await self._async_check(host, refresh_cache=False)
            return ExecutionResult(
                output=f"{update_output}\n{check.output}".strip(),
                snapshot=check.snapshot,
                reboot_required=(
                    check.snapshot.reboot_required if check.snapshot else None
                ),
            )
        if action is JobAction.REBOOT:
            _, output = await self._async_module(
                host,
                "ansible.builtin.reboot",
                become=True,
                failure_code="reboot_failed",
            )
            return ExecutionResult(output=output)
        raise AutomationExecutionError("unsupported_action", "")

    async def async_execute_custom(
        self, task: CustomTask, host: Host
    ) -> ExecutionResult:
        """Execute argv without a shell unless shell mode was explicitly stored."""
        if not task.enabled:
            raise AutomationExecutionError("custom_task_disabled", "")
        if task.mode is CustomTaskMode.COMMAND and task.argv is not None:
            _, output = await self._async_module(
                host,
                "ansible.builtin.command",
                json.dumps({"argv": task.argv}),
            )
            return ExecutionResult(output=output)
        if task.mode is CustomTaskMode.SHELL and task.shell_command is not None:
            _, output = await self._async_module(
                host, "ansible.builtin.shell", task.shell_command
            )
            return ExecutionResult(output=output)
        raise AutomationExecutionError("invalid_custom_task", "")

    async def _async_test_connection(self, host: Host) -> ExecutionResult:
        """Validate SSH, Python discovery, facts, and non-interactive sudo."""
        _, ping_output = await self._async_module(
            host,
            "ansible.builtin.ping",
            failure_code="test_connection_failed",
        )
        _, facts_output = await self._async_module(
            host,
            "ansible.builtin.setup",
            _facts_arguments(),
            failure_code="test_connection_facts_failed",
        )
        _, sudo_output = await self._async_module(
            host,
            "ansible.builtin.command",
            json.dumps({"argv": ["true"]}),
            become=True,
            failure_code="sudo_unavailable",
        )
        return ExecutionResult(
            output="\n".join((ping_output, facts_output, sudo_output))
        )

    async def _async_check(
        self, host: Host, *, refresh_cache: bool = True
    ) -> ExecutionResult:
        """Collect a locale-stable status snapshot from structured results."""
        provider = package_provider(host.package_provider)
        facts, facts_output = await self._async_module(
            host,
            "ansible.builtin.setup",
            _facts_arguments(),
            failure_code="check_updates_facts_failed",
        )
        phase_outputs = [facts_output]
        if refresh_cache:
            module, arguments = provider.cache_refresh_module
            _, refresh_output = await self._async_module(
                host,
                module,
                arguments,
                become=True,
                failure_code="check_updates_apt_cache_refresh_failed",
            )
            phase_outputs.append(refresh_output)
        packages, package_output = await self._async_module(
            host,
            "ansible.builtin.command",
            json.dumps({"argv": provider.list_command}),
            failure_code="check_updates_package_list_failed",
        )
        reboot, reboot_output = await self._async_module(
            host,
            "ansible.builtin.stat",
            "path=/var/run/reboot-required",
            failure_code="check_updates_reboot_status_failed",
        )
        package_status = provider.parse_updates(
            _string(packages.get("stdout")),
            reboot_required=_nested_bool(reboot, "stat", "exists"),
        )
        ansible_facts = facts.get("ansible_facts")
        fact_values = ansible_facts if isinstance(ansible_facts, dict) else {}
        snapshot = HostSnapshot(
            distribution=_optional_string(fact_values.get("ansible_distribution")),
            distribution_version=_optional_string(
                fact_values.get("ansible_distribution_version")
            ),
            kernel=_optional_string(fact_values.get("ansible_kernel")),
            updates=package_status.updates,
            security_updates=package_status.security_updates,
            reboot_required=package_status.reboot_required,
            status="ok",
            checked_at=datetime.now().astimezone(),
        )
        phase_outputs.extend((package_output, reboot_output))
        output = "\n".join(phase_outputs)
        return ExecutionResult(output=output, snapshot=snapshot)

    async def _async_module(
        self,
        host: Host,
        module: str,
        arguments: str | None = None,
        *,
        become: bool = False,
        failure_code: str = "ansible_failed",
    ) -> tuple[dict[str, object], str]:
        inventory = _inventory(host, self._known_hosts_path)
        callback_path = Path(__file__).with_name("ansible_plugins")
        with tempfile.TemporaryDirectory(prefix="homelab-updates-") as directory:
            working_path = Path(directory)
            inventory_path = working_path / "inventory.json"
            local_temp_path = working_path / "ansible-local"
            await asyncio.to_thread(inventory_path.write_text, json.dumps(inventory))
            await asyncio.to_thread(local_temp_path.mkdir)
            command = [
                "ansible",
                str(host.id),
                "--inventory",
                str(inventory_path),
                "--private-key",
                str(self._private_key_path),
                "--module-name",
                module,
            ]
            if arguments is not None:
                command.extend(("--args", arguments))
            if become:
                command.append("--become")
            environment = dict(os.environ)
            environment.update({
                "ANSIBLE_CALLBACK_PLUGINS": str(callback_path),
                "ANSIBLE_HOST_KEY_CHECKING": "True",
                "ANSIBLE_LOAD_CALLBACK_PLUGINS": "True",
                "ANSIBLE_LOCAL_TEMP": str(local_temp_path),
                "ANSIBLE_NOCOLOR": "True",
                "ANSIBLE_STDOUT_CALLBACK": "homelab_json",
            })
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=environment,
            )
            try:
                output_bytes, _ = await asyncio.wait_for(
                    process.communicate(), timeout=self._command_timeout
                )
            except TimeoutError as err:
                process.kill()
                await process.wait()
                raise AutomationExecutionError("execution_timeout", "") from err
        output = output_bytes.decode("utf-8", errors="replace")
        if process.returncode != 0:
            raise AutomationExecutionError(
                _classify_failure(failure_code, output),
                output,
                exit_code=process.returncode,
            )
        return _extract_module_payload(output, exit_code=process.returncode), output


def _inventory(host: Host, known_hosts_path: Path) -> dict[str, object]:
    """Build an isolated one-host inventory with silent automatic Python discovery."""
    return {
        "all": {
            "hosts": {
                str(host.id): {
                    "ansible_host": host.address,
                    "ansible_port": host.port,
                    "ansible_user": host.username,
                    "ansible_ssh_common_args": (
                        "-o StrictHostKeyChecking=accept-new "
                        f"-o UserKnownHostsFile={known_hosts_path}"
                    ),
                    "ansible_python_interpreter": "auto_silent",
                }
            }
        }
    }


def _facts_arguments() -> str:
    """Request only status and interpreter facts needed by built-in operations."""
    return json.dumps({
        "filter": [
            "ansible_distribution*",
            "ansible_kernel",
            "ansible_python*",
            "discovered_interpreter_python",
        ],
        "gather_subset": ["!all", "min"],
    })


def _extract_module_payload(
    output: str, *, exit_code: int | None = None
) -> dict[str, object]:
    """Extract one success payload from the private callback envelope."""
    serialized_results = [
        line.removeprefix(RESULT_PREFIX)
        for line in output.splitlines()
        if line.startswith(RESULT_PREFIX)
    ]
    if len(serialized_results) != 1:
        raise AutomationExecutionError(
            "invalid_ansible_output", output, exit_code=exit_code
        )
    try:
        envelope = json.loads(serialized_results[0])
    except json.JSONDecodeError as err:
        raise AutomationExecutionError(
            "invalid_ansible_output", output, exit_code=exit_code
        ) from err
    if not isinstance(envelope, dict) or envelope.get("event") != "ok":
        raise AutomationExecutionError(
            "invalid_ansible_output", output, exit_code=exit_code
        )
    payload = envelope.get("result")
    if not isinstance(payload, dict):
        raise AutomationExecutionError(
            "invalid_ansible_output", output, exit_code=exit_code
        )
    return payload


def _classify_failure(default: str, output: str) -> str:
    """Map known cross-platform failure signatures to safe stable categories."""
    lowered = output.lower()
    if any(
        marker in lowered
        for marker in (
            "failed to find a suitable python interpreter",
            "no python interpreters found",
            "python interpreter was not found",
            "the module failed to execute correctly, you probably need to set "
            "the interpreter",
            "python: not found",
            "python3: not found",
        )
    ):
        return "python_interpreter_unavailable"
    if any(
        marker in lowered
        for marker in (
            "missing sudo password",
            "sudo: not found",
            "a password is required",
            "incorrect sudo password",
        )
    ):
        return "sudo_unavailable"
    if any(
        marker in lowered
        for marker in (
            "could not get lock",
            "unable to acquire the dpkg frontend lock",
            "failed to lock apt for exclusive operation",
        )
    ):
        return "apt_lock_unavailable"
    return default


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _nested_bool(payload: dict[str, object], parent: str, child: str) -> bool:
    nested = payload.get(parent)
    return bool(nested.get(child)) if isinstance(nested, dict) else False
