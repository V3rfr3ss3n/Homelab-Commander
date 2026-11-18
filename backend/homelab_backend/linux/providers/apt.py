"""APT command/parser adapter; stable Debian/Ubuntu semantics."""

import re

from ...models import MAX_PACKAGE_DETAILS, PackageInfo
from ..domain import PackageStatus, UpdateScope


class DebianAptProvider:
    """APT behavior for supported Debian and Ubuntu hosts."""

    legacy_key = "debian_apt"
    provider_id = "linux.apt"
    scopes = frozenset({UpdateScope.FULL, UpdateScope.SINGLE, UpdateScope.SELECTED})
    cache_failure_code = "check_updates_apt_cache_refresh_failed"
    reboot_probe = ("ansible.builtin.stat", "path=/var/run/reboot-required")

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
        if any(
            not re.fullmatch(r"[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?", name)
            for name in package_names
        ):
            raise ValueError("Invalid APT package selection")
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

    def classify_failure(self, default: str, output: str) -> str:
        lowered = output.lower()
        if any(
            marker in lowered
            for marker in (
                "could not get lock",
                "unable to acquire the dpkg frontend lock",
                "failed to lock apt for exclusive operation",
            )
        ):
            return "apt_lock_unavailable"
        return default

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
