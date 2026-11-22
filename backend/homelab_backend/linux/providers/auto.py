"""Detect the system manager without trying alternative mutation backends."""

from dataclasses import replace

from ...execution.results import AutomationExecutionError, ExecutionResult
from ...models import Host
from ..ansible import AnsiblePackageTransport
from ..application import LinuxPackages
from ..domain import PackageSelection, UpdateScope
from ..ports import ModuleRunner, ProviderResolver
from .rpm import facts


class AutoProvider:
    legacy_key = "auto"
    provider_id = "linux.auto"
    scopes = frozenset(UpdateScope)

    def __init__(self, providers: ProviderResolver) -> None:
        self._providers = providers

    def classify_failure(self, default: str, output: str) -> str:
        return default

    async def _host(self, host: Host, runner: ModuleRunner) -> Host:
        detected = await facts(host, runner)
        if detected.manager == "apt" and detected.distribution in {"Debian", "Ubuntu"}:
            key = "debian_apt"
        elif detected.manager in {"dnf", "dnf4", "dnf5"}:
            key = "dnf"
        elif detected.manager == "zypper":
            key = "zypper"
        else:
            raise AutomationExecutionError("package_provider_unsupported", "")
        return host.model_copy(update={"package_provider": key})

    def _packages(self, runner: ModuleRunner) -> LinuxPackages:
        return LinuxPackages(
            AnsiblePackageTransport(runner, self._providers), self._providers
        )

    async def async_collect(
        self, host: Host, runner: ModuleRunner, *, refresh_cache: bool
    ) -> ExecutionResult:
        resolved = await self._host(host, runner)
        result = await self._packages(runner).async_check(
            resolved, refresh_cache=refresh_cache
        )
        if result.snapshot is not None and result.snapshot.package_scopes is None:
            result = replace(
                result,
                snapshot=replace(
                    result.snapshot,
                    package_scopes=tuple(sorted(s.value for s in self.scopes)),
                ),
            )
        return result

    async def async_apply(
        self, host: Host, selection: PackageSelection, runner: ModuleRunner
    ) -> ExecutionResult:
        resolved = await self._host(host, runner)
        return await self._packages(runner).async_apply(resolved, selection)
