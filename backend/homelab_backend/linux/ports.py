"""Feature-owned provider and normalized transport interfaces."""

from typing import Protocol, runtime_checkable

from ..execution.results import ExecutionResult
from ..models import Host
from .domain import Collected, LinuxFacts, PackageSelection, PackageStatus, UpdateScope


class ProviderDescriptor(Protocol):
    legacy_key: str
    provider_id: str
    scopes: frozenset[UpdateScope]

    def classify_failure(self, default: str, output: str) -> str: ...


@runtime_checkable
class PackageProvider(ProviderDescriptor, Protocol):
    legacy_key: str
    provider_id: str
    scopes: frozenset[UpdateScope]
    cache_failure_code: str
    reboot_probe: tuple[str, str]

    @property
    def update_module(self) -> tuple[str, str]: ...
    def single_update_module(self, package_name: str) -> tuple[str, str]: ...
    def selected_update_module(
        self, package_names: tuple[str, ...]
    ) -> tuple[str, str]: ...
    @property
    def cache_refresh_module(self) -> tuple[str, str]: ...
    @property
    def list_command(self) -> tuple[str, ...]: ...
    def classify_failure(self, default: str, output: str) -> str: ...
    def parse_updates(self, output: str, *, reboot_required: bool) -> PackageStatus: ...


class ModuleRunner(Protocol):
    async def async_module(
        self,
        host: Host,
        module: str,
        arguments: str | None = None,
        *,
        become: bool = False,
        failure_code: str = "ansible_failed",
    ) -> tuple[dict[str, object], str]: ...


@runtime_checkable
class InventoryProvider(ProviderDescriptor, Protocol):
    async def async_collect(
        self, host: Host, runner: ModuleRunner, *, refresh_cache: bool
    ) -> ExecutionResult: ...
    async def async_apply(
        self, host: Host, selection: PackageSelection, runner: ModuleRunner
    ) -> ExecutionResult: ...


class ProviderResolver(Protocol):
    def resolve(self, name: str) -> ProviderDescriptor: ...


class PackageTransport(Protocol):
    async def async_collect(
        self, host: Host, provider: InventoryProvider, *, refresh_cache: bool
    ) -> ExecutionResult: ...
    async def async_apply(
        self, host: Host, provider: InventoryProvider, selection: PackageSelection
    ) -> ExecutionResult: ...
    async def async_facts(self, host: Host) -> Collected[LinuxFacts]: ...
    async def async_refresh(self, host: Host, provider: PackageProvider) -> str: ...
    async def async_packages(
        self, host: Host, provider: PackageProvider
    ) -> Collected[str]: ...
    async def async_reboot(
        self, host: Host, provider: PackageProvider
    ) -> Collected[bool]: ...
    async def async_update(self, host: Host, module: tuple[str, str]) -> str: ...
