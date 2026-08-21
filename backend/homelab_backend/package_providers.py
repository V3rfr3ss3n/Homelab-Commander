"""Package-manager capabilities independent of job orchestration."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PackageStatus:
    """Normalized package and reboot state."""

    updates: int
    security_updates: int
    reboot_required: bool


class PackageProvider(Protocol):
    """Translate package-manager behavior at the execution boundary."""

    @property
    def update_module(self) -> tuple[str, str]:
        """Return the Ansible module and arguments for a full safe update."""

    def parse_updates(self, output: str, *, reboot_required: bool) -> PackageStatus:
        """Parse bounded command output into normalized counts."""


class DebianAptProvider:
    """APT behavior for supported Debian and Ubuntu hosts."""

    @property
    def update_module(self) -> tuple[str, str]:
        """Use Ansible's idempotent APT module without an implicit reboot."""
        return "ansible.builtin.apt", "update_cache=true upgrade=dist"

    def parse_updates(self, output: str, *, reboot_required: bool) -> PackageStatus:
        """Count `apt list --upgradable` package rows and security origins."""
        package_lines = tuple(
            line.strip()
            for line in output.splitlines()
            if "/" in line and "upgradable from:" in line.lower()
        )
        return PackageStatus(
            updates=len(package_lines),
            security_updates=sum("security" in line.lower() for line in package_lines),
            reboot_required=reboot_required,
        )


def package_provider(name: str) -> PackageProvider:
    """Resolve a configured provider or fail closed."""
    if name == "debian_apt":
        return DebianAptProvider()
    raise ValueError("The configured package provider is unsupported")
