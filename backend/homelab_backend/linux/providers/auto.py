"""Compose native system/Flatpak sources without owning their package catalogs."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from ...execution.results import AutomationExecutionError, ExecutionResult, HostSnapshot
from ...models import (
    MAX_PACKAGE_DETAILS,
    Host,
    PackageInfo,
    PackageSourceId,
    PackageSourceStatus,
)
from ..ansible import AnsiblePackageTransport
from ..application import LinuxPackages
from ..domain import PackageSelection, UpdateScope
from ..ports import ModuleRunner, ProviderResolver
from ..sources import selections
from .flatpak import available
from .rpm import facts


@dataclass(frozen=True, slots=True)
class Source:
    source: PackageSourceId
    host: Host


class AutoProvider:
    legacy_key = "auto"
    provider_id = "linux.auto"
    scopes = frozenset(UpdateScope)

    def __init__(self, providers: ProviderResolver) -> None:
        self._providers = providers

    def classify_failure(self, default: str, output: str) -> str:
        return default

    async def _sources(self, host: Host, runner: ModuleRunner) -> tuple[Source, ...]:
        detected = await facts(host, runner)
        chosen = host.package_sources or ("system", "flatpak_system", "flatpak_user")
        sources = []
        base = host.model_copy(
            update={
                "package_sources": None,
                "distribution": detected.distribution,
                "distribution_version": detected.version,
                "kernel": detected.kernel,
            }
        )
        if "system" in chosen:
            key = host.package_provider
            if key == "auto":
                if detected.manager == "apt" and detected.distribution in {
                    "Debian",
                    "Ubuntu",
                }:
                    key = "debian_apt"
                elif detected.manager in {"dnf", "dnf4", "dnf5"}:
                    key = "dnf"
                elif detected.manager in {"zypper", "pacman", "apk"}:
                    key = detected.manager
                else:
                    raise AutomationExecutionError("package_provider_unsupported", "")
            source: PackageSourceId
            if key == "debian_apt":
                if detected.manager != "apt" or detected.distribution not in {
                    "Debian",
                    "Ubuntu",
                }:
                    raise AutomationExecutionError("package_provider_mismatch", "")
                source = "apt"
            elif key == "dnf":
                source = "dnf"
            elif key == "zypper":
                source = "zypper"
            elif key == "apk":
                source = "apk"
            elif key == "pacman":
                source = "pacman"
            else:
                raise AutomationExecutionError("package_provider_unsupported", "")
            sources.append(
                Source(source, base.model_copy(update={"package_provider": key}))
            )
        flatpaks = tuple(s for s in ("flatpak_system", "flatpak_user") if s in chosen)
        if flatpaks:
            installed = await available(host, runner)
            if not installed and host.package_sources is not None:
                raise AutomationExecutionError("package_source_unavailable", "")
            if installed:
                sources.extend(
                    Source(source, base.model_copy(update={"package_provider": source}))
                    for source in ("flatpak_system", "flatpak_user")
                    if source in flatpaks
                )
        if not sources:
            raise AutomationExecutionError("package_source_unavailable", "")
        return tuple(sources)

    def _packages(self, runner: ModuleRunner) -> LinuxPackages:
        return LinuxPackages(
            AnsiblePackageTransport(runner, self._providers), self._providers
        )

    async def _collect(
        self, sources: tuple[Source, ...], runner: ModuleRunner, *, refresh_cache: bool
    ) -> tuple[tuple[Source, HostSnapshot], ...]:
        observations = []
        for component in sources:
            result = await self._packages(runner).async_check(
                component.host, refresh_cache=refresh_cache
            )
            if result.snapshot is None:
                raise AutomationExecutionError("package_inventory_failed", "")
            observations.append((component, result.snapshot))
        return tuple(observations)

    async def async_collect(
        self, host: Host, runner: ModuleRunner, *, refresh_cache: bool
    ) -> ExecutionResult:
        components = await self._sources(host, runner)
        observations = await self._collect(
            components, runner, refresh_cache=refresh_cache
        )
        base = observations[0][1]
        statuses = []
        per_source: list[list[PackageInfo]] = []
        for component, snapshot in observations:
            scopes = snapshot.package_scopes
            if scopes is None:
                scopes = tuple(
                    sorted(
                        s.value
                        for s in self._providers.resolve(
                            component.host.package_provider
                        ).scopes
                    )
                )
            statuses.append(
                PackageSourceStatus.model_validate({
                    "source": component.source,
                    "updates": snapshot.updates,
                    "security_updates": snapshot.security_updates,
                    "scopes": scopes,
                })
            )
            per_source.append([
                p.model_copy(
                    update={
                        "name": component.source + "::" + p.name,
                        "display_name": p.display_name or p.name,
                        "source": component.source,
                        "scopes": scopes,
                    }
                )
                for p in snapshot.packages
            ])
        # Interleave the bounded display so a large system source cannot hide Flatpak.
        rows = tuple(
            row
            for index in range(MAX_PACKAGE_DETAILS)
            for source_rows in per_source
            if index < len(source_rows)
            for row in (source_rows[index],)
        )[:MAX_PACKAGE_DETAILS]
        totals = sum(snapshot.updates for _, snapshot in observations)
        security = (
            None
            if any(s.security_updates is None for _, s in observations)
            else sum(s.security_updates or 0 for _, s in observations)
        )
        system = next(
            (s for c, s in observations if not c.source.startswith("flatpak_")), None
        )
        aggregate_scopes = tuple(
            sorted(
                s.value
                for s in UpdateScope
                if (
                    all(s.value in item.scopes for item in statuses)
                    if s is UpdateScope.FULL
                    else any(s.value in item.scopes for item in statuses)
                )
            )
        )
        snapshot = replace(
            base,
            updates=totals,
            security_updates=security,
            reboot_required=system.reboot_required if system else None,
            packages=rows,
            package_scopes=aggregate_scopes,
            package_observations=tuple(statuses),
            pacman_review=system.pacman_review if system else None,
            checked_at=datetime.now(UTC),
        )
        return ExecutionResult(
            output="Native package sources checked; no local catalog is maintained.",
            snapshot=snapshot,
        )

    async def async_apply(
        self, host: Host, selection: PackageSelection, runner: ModuleRunner
    ) -> ExecutionResult:
        components = await self._sources(host, runner)
        plans = selections(selection, frozenset(c.source for c in components))
        # Preflight every source before the first write, using live evidence.
        selected_components = tuple(c for c in components if c.source in plans)
        observations = await self._collect(
            selected_components, runner, refresh_cache=True
        )
        for component, snapshot in observations:
            plan = plans.get(component.source)
            if plan is None:
                continue
            if plan.scope not in self._providers.resolve(
                component.host.package_provider
            ).scopes or (
                snapshot.package_scopes is not None
                and plan.scope.value not in snapshot.package_scopes
            ):
                raise AutomationExecutionError("package_scope_unsupported", "")
            if plan.names and not set(plan.names) <= {
                p.name for p in snapshot.packages
            }:
                raise AutomationExecutionError("package_selection_stale", "")
        completed = 0
        reboot: bool | None = None
        for component, _snapshot in observations:
            plan = plans.get(component.source)
            if plan is None:
                continue
            try:
                result = await self._packages(runner).async_apply(component.host, plan)
            except AutomationExecutionError:
                if completed:
                    raise AutomationExecutionError(
                        "package_sources_partial_failure", ""
                    ) from None
                raise
            completed += 1
            if result.reboot_required is True:
                reboot = True
        return ExecutionResult(
            output="Selected native package source updates completed.",
            reboot_required=reboot,
        )
