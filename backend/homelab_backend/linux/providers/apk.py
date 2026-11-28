"""Alpine 3.23 package observations and explicit full upgrades."""

import re
from datetime import UTC, datetime

from ...execution.results import AutomationExecutionError, ExecutionResult, HostSnapshot
from ...models import MAX_PACKAGE_DETAILS, Host, PackageInfo
from ..domain import PackageSelection, UpdateScope
from ..ports import ModuleRunner
from .rpm import RpmFacts, command, facts, root

_APK = "/sbin/apk"
_VERSION = r"[0-9][0-9A-Za-z._+]{0,220}(?:-r[0-9]{1,12})?"
_ROW = re.compile(
    rf"([a-zA-Z0-9][a-zA-Z0-9+_.-]{{0,254}}?)-({_VERSION})"
    rf"\s+<\s+({_VERSION})(?:\s+@[a-zA-Z0-9_.-]+)?"
)


def candidates(output: str) -> tuple[PackageInfo, ...]:
    """Parse the C-locale apk-tools 3 version table without picking repositories."""
    lines = output.strip().splitlines()
    if not lines or lines[0].split() != ["Installed:", "Available:"]:
        raise AutomationExecutionError("invalid_package_output", "")
    rows: dict[str, PackageInfo] = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        match = _ROW.fullmatch(line.strip())
        if match is None or match[1] in rows:
            raise AutomationExecutionError("invalid_package_output", "")
        rows[match[1]] = PackageInfo(
            name=match[1], old_version=match[2], new_version=match[3], is_security=None
        )
    return tuple(rows[name] for name in sorted(rows))


class ApkProvider:
    legacy_key = "apk"
    provider_id = "linux.apk"
    scopes = frozenset({UpdateScope.FULL})

    def classify_failure(self, default: str, output: str) -> str:
        return default

    async def _facts(self, host: Host, runner: ModuleRunner) -> RpmFacts:
        profile = await facts(host, runner)
        if (
            profile.distribution != "Alpine"
            or profile.manager != "apk"
            or not re.fullmatch(r"3\.23(?:\.[0-9]+)?", profile.version)
        ):
            raise AutomationExecutionError("package_provider_mismatch", "")
        return profile

    async def async_collect(
        self, host: Host, runner: ModuleRunner, *, refresh_cache: bool
    ) -> ExecutionResult:
        profile = await self._facts(host, runner)
        if refresh_cache:
            await command(
                runner, host, (_APK, "update"), code="package_inventory_failed"
            )
        output, _ = await command(
            runner,
            host,
            (_APK, "version", "-l", "<"),
            code="package_inventory_failed",
            become=False,
        )
        rows = candidates(output)
        return ExecutionResult(
            output="Alpine repository inventory collected.",
            snapshot=HostSnapshot(
                distribution=profile.distribution,
                distribution_version=profile.version,
                kernel=profile.kernel,
                updates=len(rows),
                security_updates=None,
                reboot_required=None,
                status="ok",
                checked_at=datetime.now(UTC),
                packages=rows[:MAX_PACKAGE_DETAILS],
                package_scopes=("full",),
            ),
        )

    async def async_apply(
        self, host: Host, selection: PackageSelection, runner: ModuleRunner
    ) -> ExecutionResult:
        if selection.scope is not UpdateScope.FULL:
            raise AutomationExecutionError("package_scope_unsupported", "")
        await self._facts(host, runner)
        await root(host, runner)
        await command(runner, host, (_APK, "update"), code="package_inventory_failed")
        await command(
            runner,
            host,
            (_APK, "upgrade"),
            code="update_packages_failed",
            mutation=True,
        )
        return ExecutionResult(output="Alpine full package upgrade completed.")
