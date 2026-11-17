"""Package workflows depend on typed provider/transport ports, not Ansible JSON."""

from datetime import datetime

from ..execution.results import AutomationExecutionError, ExecutionResult, HostSnapshot
from ..models import Host
from .domain import PackageSelection
from .ports import PackageTransport, ProviderResolver


class LinuxPackages:
    def __init__(
        self, transport: PackageTransport, providers: ProviderResolver
    ) -> None:
        self._transport = transport
        self._providers = providers

    async def async_check(
        self, host: Host, *, refresh_cache: bool = True
    ) -> ExecutionResult:
        provider = self._providers.resolve(host.package_provider)
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

    async def async_update(
        self, host: Host, selection: PackageSelection
    ) -> ExecutionResult:
        provider = self._providers.resolve(host.package_provider)
        if selection.scope not in provider.scopes:
            raise AutomationExecutionError("package_scope_unsupported", "")
        module = (
            provider.selected_update_module(selection.names)
            if selection.names
            else provider.update_module
        )
        output = await self._transport.async_update(host, module)
        check = await self.async_check(host, refresh_cache=False)
        return ExecutionResult(
            output=f"{output}\n{check.output}".strip(),
            snapshot=check.snapshot,
            reboot_required=check.snapshot.reboot_required if check.snapshot else None,
        )
