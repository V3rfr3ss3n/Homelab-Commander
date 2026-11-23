"""Transient native source references; never a package ownership database."""

from dataclasses import dataclass

from ..execution.results import AutomationExecutionError
from ..models import PackageSourceId
from .domain import PackageSelection, UpdateScope

SOURCE_IDS: frozenset[PackageSourceId] = frozenset({
    "apt",
    "dnf",
    "zypper",
    "pacman",
    "flatpak_system",
    "flatpak_user",
})


@dataclass(frozen=True, slots=True)
class SourceTarget:
    source: PackageSourceId
    native: str | None


def target(reference: str) -> SourceTarget:
    prefix, separator, native = reference.partition("::")
    key = native if prefix == "source" else prefix
    for source in SOURCE_IDS:
        if key == source and separator and native:
            return SourceTarget(source, None if prefix == "source" else native)
    raise AutomationExecutionError("package_selection_stale", "")


def selections(
    selection: PackageSelection, available: frozenset[PackageSourceId]
) -> dict[PackageSourceId, PackageSelection]:
    if not selection.names:
        return {source: PackageSelection() for source in sorted(available)}
    grouped: dict[PackageSourceId, list[str | None]] = {}
    for reference in selection.names:
        item = target(reference)
        if item.source not in available:
            raise AutomationExecutionError("package_selection_stale", "")
        grouped.setdefault(item.source, []).append(item.native)
    result: dict[PackageSourceId, PackageSelection] = {}
    for source, names in grouped.items():
        if None in names:
            if len(names) != 1:
                raise AutomationExecutionError("invalid_package_scope", "")
            result[source] = PackageSelection()
        else:
            native = tuple(sorted(name for name in names if name is not None))
            try:
                result[source] = PackageSelection(
                    UpdateScope.SINGLE if len(native) == 1 else UpdateScope.SELECTED,
                    native,
                )
            except ValueError:
                raise AutomationExecutionError("invalid_package_scope", "") from None
    return result
