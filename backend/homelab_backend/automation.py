"""Safe asynchronous Ansible execution adapter."""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from .ansible_result import RESULT_PREFIX
from .execution.results import AutomationExecutionError as AutomationExecutionError
from .execution.results import ExecutionResult as ExecutionResult
from .execution.results import HostSnapshot as HostSnapshot
from .linux.ansible import AnsiblePackageTransport
from .linux.ansible import facts_arguments as _facts_arguments
from .linux.application import LinuxPackages
from .linux.domain import PackageSelection
from .linux.probe import PROBE_SCRIPT as _PROBE_SCRIPT
from .linux.registry import PackageProviders
from .models import CustomTask, CustomTaskMode, Host, JobAction, ProbeFacts


class AutomationExecutor(Protocol):
    """Execute one built-in operation for exactly one host."""

    async def async_execute(
        self,
        action: JobAction,
        host: Host,
        package_name: str | None = None,
        *,
        package_names: tuple[str, ...] = (),
    ) -> ExecutionResult:
        """Run the operation without blocking the event loop."""

    async def async_execute_custom(
        self, task: CustomTask, host: Host
    ) -> ExecutionResult:
        """Run one validated custom task for exactly one host."""

    async def async_probe(self, task: CustomTask, host: Host) -> ProbeFacts:
        """Read system and dependency facts without executing task commands."""


class AnsibleExecutor:
    """Run built-in Ansible modules with generated single-host inventory."""

    def __init__(
        self,
        private_key_path: Path,
        known_hosts_path: Path,
        *,
        command_timeout: float = 3600,
        package_providers: PackageProviders | None = None,
    ) -> None:
        self._private_key_path = private_key_path
        self._known_hosts_path = known_hosts_path
        self._command_timeout = command_timeout
        providers = package_providers or PackageProviders()
        self._package_transport = AnsiblePackageTransport(self, providers)
        self._linux = LinuxPackages(self._package_transport, providers)

    async def async_execute(
        self,
        action: JobAction,
        host: Host,
        package_name: str | None = None,
        *,
        package_names: tuple[str, ...] = (),
    ) -> ExecutionResult:
        """Execute a built-in action; reboot is never inferred from update."""
        if action is JobAction.TEST_CONNECTION:
            return await self._async_test_connection(host)
        if action is JobAction.CHECK_UPDATES:
            return await self._async_check(host)
        if action is JobAction.UPDATE:
            try:
                selection = PackageSelection.from_legacy(package_name, package_names)
            except ValueError:
                raise AutomationExecutionError("invalid_package_scope", "") from None
            return await self._linux.async_update(host, selection)
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
                become=task.requirements.requires_sudo,
            )
            return ExecutionResult(output=output)
        if task.mode is CustomTaskMode.SHELL and task.shell_command is not None:
            _, output = await self._async_module(
                host,
                "ansible.builtin.shell",
                task.shell_command,
                become=task.requirements.requires_sudo,
            )
            return ExecutionResult(output=output)
        raise AutomationExecutionError("invalid_custom_task", "")

    async def async_probe(self, task: CustomTask, host: Host) -> ProbeFacts:
        """Run a fixed Python probe using structured arguments and bounded time."""
        programs = list(task.requirements.programs)
        programs.append(task.argv[0] if task.argv else "/bin/sh")
        payload, _ = await self._async_module(
            host,
            "ansible.builtin.command",
            json.dumps({
                "argv": [
                    "python3",
                    "-c",
                    _PROBE_SCRIPT,
                    json.dumps({
                        "programs": programs,
                        "packages": task.requirements.packages,
                    }),
                ]
            }),
            become=task.requirements.requires_sudo,
        )
        try:
            return ProbeFacts.model_validate_json(_string(payload.get("stdout")))
        except ValidationError as err:
            raise AutomationExecutionError("invalid_probe_output", "") from err

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
        """Compatibility facade for the feature-owned package check."""
        return await self._linux.async_check(host, refresh_cache=refresh_cache)

    async def async_module(
        self,
        host: Host,
        module: str,
        arguments: str | None = None,
        *,
        become: bool = False,
        failure_code: str = "ansible_failed",
    ) -> tuple[dict[str, object], str]:
        """Transport port; delegate to the existing isolated Ansible runner."""
        return await self._async_module(
            host, module, arguments, become=become, failure_code=failure_code
        )

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
                # The container drops root privileges but may inherit root's home.
                # Keep all controller writes, including SSH sockets, in this run.
                "ANSIBLE_HOME": str(working_path),
                "ANSIBLE_LOCAL_TEMP": str(local_temp_path),
                "ANSIBLE_SSH_CONTROL_PATH_DIR": str(working_path / "ssh-control"),
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
            except (TimeoutError, asyncio.CancelledError) as err:
                process.kill()
                await process.wait()
                if isinstance(err, asyncio.CancelledError):
                    raise
                raise AutomationExecutionError("execution_timeout", "") from err
        output = output_bytes.decode("utf-8", errors="replace")
        if process.returncode != 0:
            raise AutomationExecutionError(
                self._package_transport.classify_failure(host, failure_code, output),
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
                    "ansible_ssh_use_tty": False,
                }
            }
        }
    }


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


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""
