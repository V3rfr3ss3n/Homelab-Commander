"""ALPM system inventory and whole-system maintenance, never partial upgrades."""

import re
from datetime import UTC, datetime

from ...execution.results import AutomationExecutionError, ExecutionResult, HostSnapshot
from ...models import MAX_PACKAGE_DETAILS, Host, PackageInfo
from ..domain import PackageSelection, UpdateScope
from ..ports import ModuleRunner
from .pacman_review import REVIEW_SCRIPT, split_review
from .rpm import command, facts, root


class PacmanProvider:
    legacy_key = "pacman"
    provider_id = "linux.pacman"
    scopes = frozenset({UpdateScope.FULL})

    def classify_failure(self, default: str, output: str) -> str:
        return default

    async def _facts(
        self, host: Host, runner: ModuleRunner
    ) -> tuple[str, str, str | None]:
        detected = await facts(host, runner)
        if detected.manager != "pacman" or detected.distribution not in {
            "Archlinux",
            "CachyOS",
        }:
            raise AutomationExecutionError("package_provider_mismatch", "")
        return detected.distribution, detected.version, detected.kernel

    async def async_collect(
        self, host: Host, runner: ModuleRunner, *, refresh_cache: bool
    ) -> ExecutionResult:
        distro, version, kernel = await self._facts(host, runner)
        # checkupdates owns a temporary native sync DB; never run pacman -Sy alone.
        argv = (
            ("/usr/bin/python3", "-c", REVIEW_SCRIPT)
            if refresh_cache
            else ("/usr/bin/pacman", "-Qu", "--color", "never")
        )
        output, rc = await command(
            runner,
            host,
            argv,
            code="package_inventory_failed",
            accepted=(0,) if refresh_cache else (0, 1),
            become=False,
        )
        if rc and output.strip():
            raise AutomationExecutionError("invalid_package_output", "")
        output, review = split_review(output) if refresh_cache else (output, None)
        rows = []
        seen: set[str] = set()
        for line in output.splitlines():
            if not line:
                continue
            match = re.fullmatch(
                r"([a-z0-9@_+][a-z0-9@._+-]{0,254}) ([^\s]{1,255}) -> ([^\s]{1,255})",
                line,
            )
            if match is None or match[1] in seen:
                raise AutomationExecutionError("invalid_package_output", "")
            seen.add(match[1])
            rows.append(
                PackageInfo(
                    name=match[1],
                    old_version=match[2],
                    new_version=match[3],
                    is_security=None,
                )
            )
        return ExecutionResult(
            output="ALPM repository inventory collected; AUR is excluded.",
            snapshot=HostSnapshot(
                distribution=distro,
                distribution_version=version,
                kernel=kernel,
                updates=len(rows),
                security_updates=None,
                reboot_required=None,
                status="ok",
                checked_at=datetime.now(UTC),
                packages=tuple(
                    sorted(rows, key=lambda p: p.name)[:MAX_PACKAGE_DETAILS]
                ),
                package_scopes=("full",),
                pacman_review=review,
            ),
        )

    async def async_apply(
        self, host: Host, selection: PackageSelection, runner: ModuleRunner
    ) -> ExecutionResult:
        if selection.scope is not UpdateScope.FULL:
            raise AutomationExecutionError("package_scope_unsupported", "")
        await self._facts(host, runner)
        await root(host, runner)
        await command(
            runner,
            host,
            ("/usr/bin/pacman", "-Syu", "--noconfirm"),
            code="update_packages_failed",
            mutation=True,
        )
        return ExecutionResult(
            output="ALPM full system upgrade completed; AUR is excluded."
        )
