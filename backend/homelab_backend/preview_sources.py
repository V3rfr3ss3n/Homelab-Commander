"""Disposable multi-source package simulation; no execution adapter fallback."""

from datetime import UTC, datetime

from .execution.results import AutomationExecutionError, ExecutionResult, HostSnapshot
from .linux.domain import PackageSelection, UpdateScope
from .linux.sources import selections
from .models import Host, JobAction, PackageInfo, PackageSourceId, PackageSourceStatus


def simulate_sources(
    host: Host,
    action: JobAction,
    current: tuple[PackageInfo, ...] | None,
    selection: PackageSelection,
) -> tuple[ExecutionResult, tuple[PackageInfo, ...]]:
    chosen = host.package_sources or ("system", "flatpak_system", "flatpak_user")
    keys: list[PackageSourceId] = []
    if "system" in chosen:
        if host.package_provider in {"auto", "debian_apt"}:
            keys.append("apt")
        elif host.package_provider == "pacman":
            keys.append("pacman")
        elif host.package_provider == "dnf":
            keys.append("dnf")
        else:
            keys.append("zypper")
    keys.extend(key for key in ("flatpak_system", "flatpak_user") if key in chosen)
    if current is None:
        rows: list[PackageInfo] = []
        native_keys: tuple[PackageSourceId, ...] = (
            "apt",
            "dnf",
            "zypper",
            "pacman",
            "flatpak_system",
            "flatpak_user",
        )
        for key in native_keys:
            names = (
                ("app:org.example.Editor:x86_64:stable",)
                if key.startswith("flatpak_")
                else ("curl", "vim")
            )
            rows.extend(
                PackageInfo(
                    name=key + "::" + name,
                    display_name=name.replace(":", "/")
                    if key.startswith("flatpak_")
                    else name,
                    source=key,
                    old_version="1.0",
                    new_version="2.0",
                    is_security=None,
                    scopes=("full",)
                    if key == "pacman"
                    else ("full", "selected", "single"),
                )
                for name in names
            )
        current = tuple(rows)
    if action is JobAction.UPDATE:
        plans = selections(selection, frozenset(keys))
        for key, plan in plans.items():
            if key == "pacman" and plan.scope is not UpdateScope.FULL:
                raise AutomationExecutionError("package_scope_unsupported", "")
            if plan.names and not set(plan.names) <= {
                p.name.split("::", 1)[1] for p in current if p.source == key
            }:
                raise AutomationExecutionError("package_selection_stale", "")
        current = tuple(
            p
            for p in current
            if p.source not in plans
            or (
                plans[p.source].names
                and p.name.split("::", 1)[1] not in plans[p.source].names
            )
        )
    statuses = tuple(
        PackageSourceStatus(
            source=key,
            updates=sum(p.source == key for p in current),
            scopes=("full",) if key == "pacman" else ("full", "selected", "single"),
        )
        for key in keys
    )
    scopes = (
        ("full", "selected", "single")
        if any(key != "pacman" for key in keys)
        else ("full",)
    )
    visible = tuple(p for p in current if p.source in keys)
    result = ExecutionResult(
        output="SIMULATED native sources: no connection or system change.",
        snapshot=HostSnapshot(
            distribution="CachyOS" if "pacman" in keys else "Debian",
            distribution_version="rolling" if "pacman" in keys else "12",
            kernel="synthetic",
            updates=len(visible),
            security_updates=None,
            reboot_required=False
            if action is JobAction.REBOOT
            else host.reboot_required,
            status="ok",
            checked_at=datetime.now(UTC),
            packages=visible,
            package_scopes=scopes,
            package_observations=statuses,
        ),
    )

    return result, current
