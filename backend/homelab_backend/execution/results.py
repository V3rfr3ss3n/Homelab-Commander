"""Provider-neutral immutable executor results and classified safe failures."""

from dataclasses import dataclass
from datetime import datetime

from ..models import PackageInfo, PackageSourceStatus, PacmanReview


@dataclass(frozen=True, slots=True)
class HostSnapshot:
    """Normalized status collected by an execution adapter."""

    distribution: str | None
    distribution_version: str | None
    kernel: str | None
    updates: int
    security_updates: int | None
    reboot_required: bool | None
    status: str
    checked_at: datetime
    packages: tuple[PackageInfo, ...] = ()

    package_scopes: tuple[str, ...] | None = None
    package_observations: tuple[PackageSourceStatus, ...] = ()
    pacman_review: PacmanReview | None = None

    def __post_init__(self) -> None:
        """Reject contradictory adapter snapshots before they replace stored status."""
        if not (
            self.updates >= 0
            and len(self.packages) <= self.updates
            and (
                self.security_updates is None
                or (
                    0 <= self.security_updates <= self.updates
                    and sum(package.is_security is True for package in self.packages)
                    <= self.security_updates
                )
            )
        ):
            raise ValueError("Package snapshot counts do not match its rows")


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Bounded executor result consumed by the job service."""

    output: str
    snapshot: HostSnapshot | None = None
    reboot_required: bool | None = None
    exit_code: int = 0


class AutomationExecutionError(Exception):
    """Safe execution failure with bounded diagnostic output."""

    def __init__(self, code: str, output: str, *, exit_code: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.output = output
        self.exit_code = exit_code
