"""Package workflows depend on typed provider/transport ports, not Ansible JSON."""

from dataclasses import replace
from datetime import datetime

from ..execution.results import AutomationExecutionError, ExecutionResult, HostSnapshot
from ..models import Host
from .domain import PackageSelection
from .ports import (
    InventoryProvider,
    PackageProvider,
    PackageTransport,
    ProviderResolver,
)


class LinuxPackages:
    def __init__(
        self, transport: PackageTransport, providers: ProviderResolver
    ) -> None:
        self._transport = transport
        self._providers = providers

    async def async_check(
        self, host: Host, *, refresh_cache: bool = True
    ) -> ExecutionResult:
        provider = self._providers.resolve(
            "auto" if host.package_sources is not None else host.package_provider
        )
        if isinstance(provider, InventoryProvider):
            return await self._transport.async_collect(
                host, provider, refresh_cache=refresh_cache
            )
        if not isinstance(provider, PackageProvider):
            raise AutomationExecutionError("package_provider_unsupported", "")
        facts = await self._transport.async_facts(host)
        outputs = [facts.output]
        if refresh_cache:
            outputs.append(await self._transport.async_refresh(host, provider))
        packages = await self._transport.async_packages(host, provider)
        reboot = await self._transport.async_reboot(host, provider)
        try:
            status = provider.parse_updates(
                packages.value, reboot_required=reboot.value
            )
        except ValueError:
            raise AutomationExecutionError("invalid_package_output", "") from None
        snapshot = HostSnapshot(
            distribution=facts.value.distribution,
            distribution_version=facts.value.distribution_version,
            kernel=facts.value.kernel,
            updates=status.updates,
            security_updates=status.security_updates,
            reboot_required=status.reboot_required,
            status="ok",
            checked_at=datetime.now().astimezone(),
            packages=status.packages,
        )
        outputs.extend((packages.output, reboot.output))
        return ExecutionResult(output="\n".join(outputs), snapshot=snapshot)

    async def async_apply(
        self, host: Host, selection: PackageSelection
    ) -> ExecutionResult:
        """Apply exactly once; the caller collects the resulting observation."""
        provider = self._providers.resolve(
            "auto" if host.package_sources is not None else host.package_provider
        )
        if selection.scope not in provider.scopes:
            raise AutomationExecutionError("package_scope_unsupported", "")
        reboot_required: bool | None = None
        if isinstance(provider, InventoryProvider):
            applied = await self._transport.async_apply(host, provider, selection)
            output = applied.output
            reboot_required = applied.reboot_required
        elif isinstance(provider, PackageProvider):
            try:
                module = (
                    provider.selected_update_module(selection.names)
                    if selection.names
                    else provider.update_module
                )
            except ValueError:
                raise AutomationExecutionError("invalid_package_scope", "") from None
            output = await self._transport.async_update(host, module)
        else:
            raise AutomationExecutionError("package_provider_unsupported", "")
        return ExecutionResult(output=output, reboot_required=reboot_required)

    async def async_update(
        self, host: Host, selection: PackageSelection
    ) -> ExecutionResult:
        applied = await self.async_apply(host, selection)
        check = await self.async_check(host, refresh_cache=False)
        if applied.reboot_required is True and check.snapshot is not None:
            check = replace(
                check, snapshot=replace(check.snapshot, reboot_required=True)
            )
        return ExecutionResult(
            output=f"{applied.output}\n{check.output}".strip(),
            snapshot=check.snapshot,
            reboot_required=check.snapshot.reboot_required if check.snapshot else None,
        )
