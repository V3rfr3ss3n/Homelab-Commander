"""Normalize Ansible payloads once at the Linux infrastructure boundary."""

import json

from ..execution.results import ExecutionResult
from ..models import Host
from .domain import Collected, LinuxFacts, PackageSelection
from .ports import (
    InventoryProvider,
    ModuleRunner,
    PackageProvider,
    ProviderDescriptor,
    ProviderResolver,
)


class AnsiblePackageTransport:
    def __init__(self, runner: ModuleRunner, providers: ProviderResolver) -> None:
        self._runner = runner
        self._providers = providers

    async def async_collect(
        self, host: Host, provider: InventoryProvider, *, refresh_cache: bool
    ) -> ExecutionResult:
        return await provider.async_collect(
            host, self._runner, refresh_cache=refresh_cache
        )

    async def async_apply(
        self, host: Host, provider: InventoryProvider, selection: PackageSelection
    ) -> ExecutionResult:
        return await provider.async_apply(host, selection, self._runner)

    async def async_facts(self, host: Host) -> Collected[LinuxFacts]:
        payload, output = await self._runner.async_module(
            host,
            "ansible.builtin.setup",
            facts_arguments(),
            failure_code="check_updates_facts_failed",
        )
        facts = payload.get("ansible_facts")
        values = facts if isinstance(facts, dict) else {}
        return Collected(
            LinuxFacts(
                _optional_string(values.get("ansible_distribution")),
                _optional_string(values.get("ansible_distribution_version")),
                _optional_string(values.get("ansible_kernel")),
            ),
            output,
        )

    async def async_refresh(self, host: Host, provider: PackageProvider) -> str:
        module, arguments = provider.cache_refresh_module
        _, output = await self._runner.async_module(
            host,
            module,
            arguments,
            become=True,
            failure_code=provider.cache_failure_code,
        )
        return output

    async def async_packages(
        self, host: Host, provider: PackageProvider
    ) -> Collected[str]:
        payload, output = await self._runner.async_module(
            host,
            "ansible.builtin.command",
            json.dumps({"argv": provider.list_command}),
            failure_code="check_updates_package_list_failed",
        )
        value = payload.get("stdout")
        return Collected(value if isinstance(value, str) else "", output)

    async def async_reboot(
        self, host: Host, provider: PackageProvider
    ) -> Collected[bool]:
        module, arguments = provider.reboot_probe
        payload, output = await self._runner.async_module(
            host, module, arguments, failure_code="check_updates_reboot_status_failed"
        )
        status = payload.get("stat")
        return Collected(
            bool(status.get("exists")) if isinstance(status, dict) else False, output
        )

    async def async_update(self, host: Host, module: tuple[str, str]) -> str:
        name, arguments = module
        _, output = await self._runner.async_module(
            host, name, arguments, become=True, failure_code="update_packages_failed"
        )
        return output

    def classify_failure(self, host: Host, default: str, output: str) -> str:
        try:
            provider = self._providers.resolve(host.package_provider)
        except ValueError:
            provider = None
        return classify_failure(default, output, provider)


def facts_arguments() -> str:
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


def classify_failure(
    default: str, output: str, provider: ProviderDescriptor | None
) -> str:
    """Map known cross-platform failure signatures to safe stable categories."""
    lowered = output.lower()
    if any(
        marker in lowered
        for marker in (
            "failed to find a suitable python interpreter",
            "no python interpreters found",
            "python interpreter was not found",
            (
                "the module failed to execute correctly, you probably need to set "
                "the interpreter"
            ),
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
    return provider.classify_failure(default, output) if provider else default


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
