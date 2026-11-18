"""Immutable Linux package values; no transport, provider JSON or I/O."""

import re
from dataclasses import dataclass
from enum import StrEnum

from ..models import MAX_PACKAGE_DETAILS, PackageInfo


class UpdateScope(StrEnum):
    FULL = "full"
    SINGLE = "single"
    SELECTED = "selected"


@dataclass(frozen=True, slots=True)
class PackageSelection:
    scope: UpdateScope = UpdateScope.FULL
    names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.scope, UpdateScope) or not isinstance(self.names, tuple):
            raise ValueError("Invalid package operation scope")
        if any(not isinstance(name, str) for name in self.names):
            raise ValueError("Invalid package operation scope")
        expected = (
            (self.scope is UpdateScope.FULL and not self.names)
            or (self.scope is UpdateScope.SINGLE and len(self.names) == 1)
            or (
                self.scope is UpdateScope.SELECTED
                and 1 <= len(self.names) <= MAX_PACKAGE_DETAILS
            )
        )
        if (
            not expected
            or len(set(self.names)) != len(self.names)
            or any(
                not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+_.:-]*", name)
                or len(name) > 255
                for name in self.names
            )
        ):
            raise ValueError("Invalid package operation scope")

    @classmethod
    def from_legacy(
        cls, package_name: str | None, package_names: tuple[str, ...]
    ) -> PackageSelection:
        if package_name is not None and package_names:
            raise ValueError("Package scopes are mutually exclusive")
        if package_names:
            return cls(UpdateScope.SELECTED, tuple(sorted(package_names)))
        if package_name is not None:
            return cls(UpdateScope.SINGLE, (package_name,))
        return cls()


@dataclass(frozen=True, slots=True)
class PackageStatus:
    updates: int
    security_updates: int
    reboot_required: bool
    packages: tuple[PackageInfo, ...] = ()

    def __post_init__(self) -> None:
        if not (
            0 <= self.security_updates <= self.updates
            and len(self.packages) <= min(self.updates, MAX_PACKAGE_DETAILS)
            and all(p.is_security is not None for p in self.packages)
            and sum(p.is_security is True for p in self.packages)
            <= self.security_updates
        ):
            raise ValueError("Package snapshot counts do not match its rows")


@dataclass(frozen=True, slots=True)
class LinuxFacts:
    distribution: str | None
    distribution_version: str | None
    kernel: str | None


@dataclass(frozen=True, slots=True)
class Collected[T]:
    value: T
    output: str
