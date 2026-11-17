"""Provider-neutral observation contract; never coerce missing evidence to zero.

This internal successor contract is not the legacy HTTP/SQLite status schema.
Future providers must preserve evidence states through their API/UI rollout.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

from ..models import MAX_PACKAGE_DETAILS, PackageInfo
from .domain import PackageStatus


class EvidenceState(StrEnum):
    KNOWN = "known"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class ObservedValue[T: (int, bool)]:
    state: EvidenceState
    value: T | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        valid = (
            type(self.value) in (int, bool) and self.reason is None
            if self.state is EvidenceState.KNOWN
            else self.value is None
            and isinstance(self.reason, str)
            and re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", self.reason)
        )
        if not isinstance(self.state, EvidenceState) or not valid:
            raise ValueError("Invalid package observation evidence")


def _boolean(observation: ObservedValue[bool]) -> None:
    if not isinstance(observation, ObservedValue) or (
        observation.state is EvidenceState.KNOWN and type(observation.value) is not bool
    ):
        raise ValueError("Invalid boolean observation")


@dataclass(frozen=True, slots=True)
class PackageEvidence:
    name: str
    old_version: str
    new_version: str
    security: ObservedValue[bool]

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value or len(value) > 255
            for value in (self.name, self.old_version, self.new_version)
        ):
            raise ValueError("Invalid normalized package detail")
        _boolean(self.security)


@dataclass(frozen=True, slots=True)
class InventoryEvidence:
    """A successful inventory collection, with independently qualified signals.

    Collection failures raise instead of constructing an empty inventory. Totals
    cover every pending package; details remain bounded and may be incomplete.
    """

    total: int
    security: ObservedValue[int]
    reboot: ObservedValue[bool]
    packages: tuple[PackageEvidence, ...] = ()

    def __post_init__(self) -> None:
        if (
            type(self.total) is not int
            or self.total < 0
            or not isinstance(self.packages, tuple)
            or len(self.packages) > min(self.total, MAX_PACKAGE_DETAILS)
            or any(not isinstance(p, PackageEvidence) for p in self.packages)
            or len({p.name for p in self.packages}) != len(self.packages)
        ):
            raise ValueError("Invalid package inventory counts")
        if not isinstance(self.security, ObservedValue) or (
            self.security.state is EvidenceState.KNOWN
            and (
                type(self.security.value) is not int
                or not 0 <= self.security.value <= self.total
                or sum(p.security.value is True for p in self.packages)
                > self.security.value
            )
        ):
            raise ValueError("Invalid security inventory count")
        _boolean(self.reboot)

    @property
    def details_complete(self) -> bool:
        return len(self.packages) == self.total

    def to_legacy(self) -> PackageStatus:
        """Fail closed where the v1 status cannot express qualified evidence."""
        if (
            self.security.value is None
            or self.reboot.value is None
            or any(p.security.value is None for p in self.packages)
        ):
            raise ValueError("Legacy status cannot represent missing evidence")
        return PackageStatus(
            self.total,
            self.security.value,
            self.reboot.value,
            tuple(
                PackageInfo(
                    name=p.name,
                    old_version=p.old_version,
                    new_version=p.new_version,
                    is_security=p.security.value is True,
                )
                for p in self.packages
            ),
        )

    @classmethod
    def from_legacy(cls, status: PackageStatus) -> InventoryEvidence:
        """Preserve reported legacy signals, without upgrading their provenance.

        APT origin matching/file absence are legacy heuristics, not an authoritative
        advisory feed or proof that every process uses current code.
        """
        return cls(
            status.updates,
            ObservedValue(EvidenceState.KNOWN, status.security_updates),
            ObservedValue(EvidenceState.KNOWN, status.reboot_required),
            tuple(
                PackageEvidence(
                    p.name,
                    p.old_version,
                    p.new_version,
                    ObservedValue(EvidenceState.KNOWN, p.is_security),
                )
                for p in status.packages
            ),
        )
