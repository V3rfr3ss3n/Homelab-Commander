"""Package-manager capabilities independent of job orchestration."""

import re
from dataclasses import dataclass
from typing import Protocol

from .models import MAX_PACKAGE_DETAILS, PackageInfo


@dataclass(frozen=True, slots=True)
class PackageStatus:
    """Normalized package and reboot state."""

    updates: int
    security_updates: int
    reboot_required: bool
    packages: tuple[PackageInfo, ...] = ()


class PackageProvider(Protocol):
    """Translate package-manager behavior at the execution boundary."""

    @property
    def update_module(self) -> tuple[str, str]:
        """Return the Ansible module and arguments for a full safe update."""

    def single_update_module(self, package_name: str) -> tuple[str, str]:
        """Return the Ansible module and arguments for one selected package."""

    def selected_update_module(self, package_names: tuple[str, ...]) -> tuple[str, str]:
        """Return the module for an explicitly bounded package selection."""

    @property
    def cache_refresh_module(self) -> tuple[str, str]:
        """Return the privileged module used to refresh package metadata."""

    @property
    def list_command(self) -> tuple[str, ...]:
        """Return the locale-stable argv used to list available updates."""

    def parse_updates(self, output: str, *, reboot_required: bool) -> PackageStatus:
        """Parse bounded command output into normalized counts."""


class DebianAptProvider:
    """APT behavior for supported Debian and Ubuntu hosts."""

    @property
    def update_module(self) -> tuple[str, str]:
        """Use Ansible's idempotent APT module without an implicit reboot."""
        return "ansible.builtin.apt", "update_cache=true upgrade=dist"

    def single_update_module(self, package_name: str) -> tuple[str, str]:
        """Install or update exactly one validated APT package."""
        return (
            "ansible.builtin.apt",
            f"update_cache=true name={package_name} state=latest only_upgrade=true",
        )

    def selected_update_module(self, package_names: tuple[str, ...]) -> tuple[str, str]:
        """Update selected installed packages, letting APT resolve dependencies."""
        if not package_names:
            raise ValueError("Package selection must not be empty")
        return self.single_update_module(",".join(package_names))

    @property
    def cache_refresh_module(self) -> tuple[str, str]:
        """Refresh APT metadata without installing packages."""
        return "ansible.builtin.apt", "update_cache=true cache_valid_time=0"

    @property
    def list_command(self) -> tuple[str, ...]:
        """Force stable English output without invoking a shell."""
        return (
            "/usr/bin/env",
            "LC_ALL=C",
            "LANG=C",
            "/usr/bin/apt",
            "list",
            "--upgradable",
        )

    def parse_updates(self, output: str, *, reboot_required: bool) -> PackageStatus:
        """Count `apt list --upgradable` package rows and security origins."""
        package_lines = tuple(
            line.strip()
            for line in output.splitlines()
            if "/" in line and "upgradable from:" in line.lower()
        )
        parsed: list[PackageInfo] = []
        for line in package_lines:
            match = re.match(
                r"^(?P<name>[^/\s]+)/(?P<origin>\S+)\s+(?P<new>\S+)\s+"
                r"\S+\s+\[upgradable from: (?P<old>[^\]]+)\]",
                line,
                re.IGNORECASE,
            )
            if match is None:
                continue
            parsed.append(
                PackageInfo(
                    name=match.group("name"),
                    old_version=match.group("old"),
                    new_version=match.group("new"),
                    is_security="security" in match.group("origin").lower(),
                )
            )
        return PackageStatus(
            updates=len(package_lines),
            security_updates=sum("security" in line.lower() for line in package_lines),
            reboot_required=reboot_required,
            packages=tuple(parsed[:MAX_PACKAGE_DETAILS]),
        )


def package_provider(name: str) -> PackageProvider:
    """Resolve a configured provider or fail closed."""
    if name == "debian_apt":
        return DebianAptProvider()
    raise ValueError("The configured package provider is unsupported")
