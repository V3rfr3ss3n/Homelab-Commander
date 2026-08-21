"""Safe asynchronous Ansible execution adapter."""

import asyncio
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

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

    def __init__(self, code: str, output: str) -> None:
        super().__init__(code)
        self.code = code
        self.output = output


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
            _, output = await self._async_module(host, "ansible.builtin.ping")
            return ExecutionResult(output=output)
        if action is JobAction.CHECK_UPDATES:
            return await self._async_check(host)
        if action is JobAction.UPDATE:
            provider = package_provider(host.package_provider)
            module, arguments = provider.update_module
            _, update_output = await self._async_module(
                host, module, arguments, become=True
            )
            check = await self._async_check(host)
            return ExecutionResult(
                output=f"{update_output}\n{check.output}".strip(),
                snapshot=check.snapshot,
                reboot_required=(
                    check.snapshot.reboot_required if check.snapshot else None
                ),
            )
        if action is JobAction.REBOOT:
            _, output = await self._async_module(
                host, "ansible.builtin.reboot", become=True
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

    async def _async_check(self, host: Host) -> ExecutionResult:
        facts, facts_output = await self._async_module(
            host,
            "ansible.builtin.setup",
            "filter=ansible_distribution*",
        )
        packages, package_output = await self._async_module(
            host,
            "ansible.builtin.command",
            json.dumps({"argv": ["apt", "list", "--upgradable"]}),
        )
        reboot, reboot_output = await self._async_module(
            host,
            "ansible.builtin.stat",
            "path=/var/run/reboot-required",
        )
        package_status = package_provider(host.package_provider).parse_updates(
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
        output = "\n".join((facts_output, package_output, reboot_output))
        return ExecutionResult(output=output, snapshot=snapshot)

    async def _async_module(
        self,
        host: Host,
        module: str,
        arguments: str | None = None,
        *,
        become: bool = False,
    ) -> tuple[dict[str, object], str]:
        inventory = {
            "all": {
                "hosts": {
                    str(host.id): {
                        "ansible_host": host.address,
                        "ansible_port": host.port,
                        "ansible_user": host.username,
                        "ansible_ssh_common_args": (
                            "-o StrictHostKeyChecking=accept-new "
                            f"-o UserKnownHostsFile={self._known_hosts_path}"
                        ),
                    }
                }
            }
        }
        with tempfile.TemporaryDirectory(prefix="homelab-updates-") as directory:
            inventory_path = Path(directory) / "inventory.json"
            await asyncio.to_thread(inventory_path.write_text, json.dumps(inventory))
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
            environment["ANSIBLE_HOST_KEY_CHECKING"] = "True"
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
            raise AutomationExecutionError("ansible_failed", output)
        return _extract_module_payload(output), output


def _extract_module_payload(output: str) -> dict[str, object]:
    """Extract the JSON object from normal Ansible ad-hoc output."""
    start = output.find("{")
    end = output.rfind("}")
    if start < 0 or end <= start:
        raise AutomationExecutionError("invalid_ansible_output", output)
    try:
        payload = json.loads(output[start : end + 1])
    except json.JSONDecodeError as err:
        raise AutomationExecutionError("invalid_ansible_output", output) from err
    if not isinstance(payload, dict):
        raise AutomationExecutionError("invalid_ansible_output", output)
    return payload


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _nested_bool(payload: dict[str, object], parent: str, child: str) -> bool:
    nested = payload.get(parent)
    return bool(nested.get(child)) if isinstance(nested, dict) else False
