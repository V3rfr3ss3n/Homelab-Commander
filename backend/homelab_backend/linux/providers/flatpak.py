"""Native Flatpak observations; no remote editing or locally owned package map."""

import json
import re
from datetime import UTC, datetime
from typing import Literal

from ...execution.results import AutomationExecutionError, ExecutionResult, HostSnapshot
from ...models import MAX_PACKAGE_DETAILS, Host, PackageInfo
from ..domain import PackageSelection, UpdateScope
from ..ports import ModuleRunner
from .rpm import command

# A complete ref is reconstructed only from validated, unambiguous components.
_REF = re.compile(
    r"(app|runtime)/([A-Za-z0-9_][A-Za-z0-9_.-]*)/([A-Za-z0-9_][A-Za-z0-9_.-]*)/([A-Za-z0-9_][A-Za-z0-9_.-]*)"
)
_COMMIT = re.compile(r"(?:[0-9a-f]{12}|[0-9a-f]{64})")
_ORIGIN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,254}")


async def available(host: Host, runner: ModuleRunner) -> bool:
    payload, _ = await runner.async_module(
        host,
        "ansible.builtin.stat",
        json.dumps({"path": "/usr/bin/flatpak", "follow": True}),
        failure_code="package_detection_failed",
    )
    stat = payload.get("stat")
    if not isinstance(stat, dict) or type(stat.get("exists")) is not bool:
        raise AutomationExecutionError("package_detection_failed", "")
    if not stat["exists"]:
        return False
    if stat.get("isreg") is not True or stat.get("executable") is not True:
        raise AutomationExecutionError("package_source_unavailable", "")
    return True


def records(output: str, kind: str) -> dict[tuple[str, str], str]:
    rows: dict[tuple[str, str], str] = {}
    for line in output.splitlines():
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) != 3:
            raise AutomationExecutionError("invalid_package_output", "")
        ref, commit, origin = fields
        # `list --columns=ref` emits a partial ref; remote-ls emits the full ref.
        if ref.count("/") == 2:
            ref = kind + "/" + ref
        if (
            not _REF.fullmatch(ref)
            or not ref.startswith(kind + "/")
            or len(ref) > 215
            or not _COMMIT.fullmatch(commit)
            or not _ORIGIN.fullmatch(origin)
            or (ref, origin) in rows
        ):
            raise AutomationExecutionError("invalid_package_output", "")
        rows[ref, origin] = commit
    return rows


class FlatpakProvider:
    scopes = frozenset(UpdateScope)

    def __init__(self, installation: Literal["system", "user"]) -> None:
        self.installation = installation
        self.legacy_key = "flatpak_" + installation
        self.provider_id = "linux." + self.legacy_key

    def classify_failure(self, default: str, output: str) -> str:
        return default

    @property
    def _prefix(self) -> tuple[str, ...]:
        return ("/usr/bin/flatpak", "--" + self.installation)

    async def async_collect(
        self, host: Host, runner: ModuleRunner, *, refresh_cache: bool
    ) -> ExecutionResult:
        native: dict[tuple[str, str], str] = {}
        updates: dict[tuple[str, str], str] = {}
        for kind in ("app", "runtime"):
            installed, _ = await command(
                runner,
                host,
                (
                    *self._prefix,
                    "list",
                    "--all",
                    "--" + kind,
                    "--columns=ref:f,active:f,origin:f",
                ),
                code="package_inventory_failed",
                become=False,
            )
            installed_records = records(installed, kind)
            native.update(installed_records)
            if not installed_records:
                continue
            # Ask the manager for live evidence; do not compare an owned catalog.
            pending, _ = await command(
                runner,
                host,
                (
                    *self._prefix,
                    "remote-ls",
                    "--updates",
                    "--all",
                    "--" + kind,
                    "--arch=*",
                    "--columns=ref:f,commit:f,origin:f",
                ),
                code="package_inventory_failed",
                become=False,
            )
            updates.update(records(pending, kind))
        rows = []
        seen: set[str] = set()
        for (ref, origin), commit in updates.items():
            old = native.get((ref, origin))
            if old is None:
                continue
            if ref in seen:
                raise AutomationExecutionError("invalid_package_output", "")
            seen.add(ref)
            rows.append(
                PackageInfo(
                    name=ref.replace("/", ":"),
                    display_name=ref,
                    old_version=old,
                    new_version=commit,
                    is_security=None,
                )
            )
        return ExecutionResult(
            output="Flatpak inventory collected.",
            snapshot=HostSnapshot(
                distribution=host.distribution,
                distribution_version=host.distribution_version,
                kernel=host.kernel,
                updates=len(rows),
                security_updates=None,
                reboot_required=None,
                status="ok",
                checked_at=datetime.now(UTC),
                packages=tuple(
                    sorted(rows, key=lambda p: p.name)[:MAX_PACKAGE_DETAILS]
                ),
                package_scopes=tuple(sorted(s.value for s in self.scopes)),
            ),
        )

    async def async_apply(
        self, host: Host, selection: PackageSelection, runner: ModuleRunner
    ) -> ExecutionResult:
        # Fresh native inventory authorizes exact installed refs, never the UI cache.
        current = await self.async_collect(host, runner, refresh_cache=True)
        assert current.snapshot is not None
        eligible = {p.name for p in current.snapshot.packages}
        if selection.names and not set(selection.names) <= eligible:
            raise AutomationExecutionError("package_selection_stale", "")
        refs = tuple(name.replace(":", "/") for name in selection.names)
        if any(not _REF.fullmatch(ref) for ref in refs):
            raise AutomationExecutionError("invalid_package_scope", "")
        await command(
            runner,
            host,
            (*self._prefix, "update", "--noninteractive", "--assumeyes", *refs),
            code="update_packages_failed",
            mutation=True,
            become=self.installation == "system",
        )
        return ExecutionResult(output="Flatpak update completed.")
