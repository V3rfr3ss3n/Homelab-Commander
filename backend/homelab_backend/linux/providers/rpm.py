"""Bounded RPM inventory adapters and explicit argv maintenance operations."""

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime

from ...execution.results import AutomationExecutionError, ExecutionResult, HostSnapshot
from ...models import MAX_PACKAGE_DETAILS, Host, PackageInfo
from ..domain import PackageSelection, UpdateScope
from ..evidence import EvidenceState, InventoryEvidence, ObservedValue, PackageEvidence
from ..ports import ModuleRunner
from .rpm_command import COMMAND_SCRIPT

_RPM_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9+_.-]{0,254}")
_FORMAT = "%{NAME}|%{ARCH}|%{EPOCHNUM}:%{VERSION}-%{RELEASE}\\n"
_SCOPES = frozenset(UpdateScope)


def _fail(code: str, rc: int | None = None) -> AutomationExecutionError:
    return AutomationExecutionError(code, "", exit_code=rc)


async def command(
    runner: ModuleRunner,
    host: Host,
    argv: tuple[str, ...],
    *,
    code: str,
    accepted: tuple[int, ...] | None = (0,),
    mutation: bool = False,
) -> tuple[str, int]:
    try:
        payload, _ = await runner.async_module(
            host,
            "ansible.builtin.command",
            json.dumps({
                "argv": [
                    "/usr/bin/python3",
                    "-c",
                    COMMAND_SCRIPT,
                    json.dumps({
                        "argv": argv,
                        "timeout": 3500 if mutation else 180,
                    }),
                ],
            }),
            become=True,
            failure_code=code,
        )
    except AutomationExecutionError as error:
        raise _fail(error.code, error.exit_code) from None
    try:
        raw = payload.get("stdout")
        if not isinstance(raw, str) or len(raw) > 3_000_000:
            raise ValueError
        result = json.loads(raw)
        if (
            not isinstance(result, dict)
            or type(result.get("rc")) is not int
            or not isinstance(result.get("stdout"), str)
        ):
            raise ValueError
        rc, output = result["rc"], result["stdout"]
        if len(output) > 2_097_152:
            raise ValueError
    except ValueError, TypeError:
        raise _fail("invalid_package_output") from None
    if accepted is not None and rc not in accepted:
        raise _fail(code, rc)
    return output, rc


@dataclass(frozen=True, slots=True)
class RpmFacts:
    distribution: str
    version: str
    kernel: str | None
    manager: str


async def facts(host: Host, runner: ModuleRunner) -> RpmFacts:
    try:
        payload, _ = await runner.async_module(
            host,
            "ansible.builtin.setup",
            json.dumps({
                "filter": [
                    "ansible_distribution*",
                    "ansible_kernel",
                    "ansible_pkg_mgr",
                ],
                "gather_subset": ["!all", "min"],
            }),
            failure_code="package_detection_failed",
        )
    except AutomationExecutionError as error:
        raise _fail(error.code, error.exit_code) from None
    value = payload.get("ansible_facts")
    if not isinstance(value, dict):
        raise _fail("package_detection_failed")
    distro, version, manager = (
        value.get(key)
        for key in (
            "ansible_distribution",
            "ansible_distribution_version",
            "ansible_pkg_mgr",
        )
    )
    if not all(isinstance(v, str) and v for v in (distro, version, manager)):
        raise _fail("package_detection_failed")
    if (
        len(str(distro)) > 100
        or not re.fullmatch(r"[0-9][A-Za-z0-9._+-]{0,99}", str(version))
        or len(str(manager)) > 30
    ):
        raise _fail("package_detection_failed")
    kernel = value.get("ansible_kernel")
    return RpmFacts(
        str(distro),
        str(version),
        kernel if isinstance(kernel, str) and len(kernel) <= 255 else None,
        str(manager),
    )


async def root(host: Host, runner: ModuleRunner) -> None:
    output, _ = await command(
        runner, host, ("/usr/bin/id", "-u"), code="sudo_unavailable"
    )
    if output.strip() != "0":
        raise _fail("sudo_unavailable")


def rpm_rows(output: str) -> dict[str, str]:
    """Strict formatted RPM records, retaining multiple installed kernel versions."""
    rows: dict[str, list[str]] = {}
    for line in output.splitlines():
        fields = line.split("|")
        if len(fields) != 3:
            raise _fail("invalid_package_output")
        name, arch, version = fields
        if (
            not _RPM_NAME.fullmatch(name)
            or not re.fullmatch(r"[A-Za-z0-9_]+", arch)
            or not version
            or len(version) > 255
        ):
            raise _fail("invalid_package_output")
        rows.setdefault(name + "." + arch, []).append(version)
    return {name: ", ".join(sorted(set(versions))) for name, versions in rows.items()}


async def installed(
    host: Host, runner: ModuleRunner, names: tuple[str, ...]
) -> dict[str, str]:
    if not names:
        return {}
    output, _ = await command(
        runner,
        host,
        ("/usr/bin/rpm", "-q", "--queryformat", _FORMAT, "--", *names),
        code="package_inventory_failed",
    )
    values = rpm_rows(output)
    if set(values) != set(names):
        raise _fail("package_selection_stale")
    return values


def snapshot(
    f: RpmFacts,
    names: dict[str, str],
    old: dict[str, str],
    reboot: bool | None,
    scopes: frozenset[UpdateScope],
) -> ExecutionResult:
    unknown: ObservedValue[bool] = ObservedValue(
        EvidenceState.UNKNOWN, reason="linux.security_unverified"
    )
    evidence = InventoryEvidence(
        len(names),
        ObservedValue(EvidenceState.UNKNOWN, reason="linux.security_unverified"),
        ObservedValue(EvidenceState.UNKNOWN, reason="linux.reboot_unverified")
        if reboot is None
        else ObservedValue(EvidenceState.KNOWN, reboot),
        tuple(
            PackageEvidence(name, old[name], names[name], unknown)
            for name in sorted(names)[:MAX_PACKAGE_DETAILS]
        ),
    )
    return ExecutionResult(
        output="Package inventory collected; security classification is unknown.",
        snapshot=HostSnapshot(
            distribution=f.distribution,
            distribution_version=f.version,
            kernel=f.kernel,
            updates=evidence.total,
            security_updates=evidence.security.value,
            reboot_required=evidence.reboot.value,
            status="ok",
            checked_at=datetime.now(UTC),
            packages=tuple(
                PackageInfo(
                    name=p.name,
                    old_version=p.old_version,
                    new_version=p.new_version,
                    is_security=None,
                )
                for p in evidence.packages
            ),
            package_scopes=tuple(sorted(s.value for s in scopes)),
        ),
        reboot_required=reboot,
    )


class DnfProvider:
    legacy_key = "dnf"
    provider_id = "linux.dnf"
    scopes = _SCOPES

    def classify_failure(self, default: str, output: str) -> str:
        return default

    def _binary(self, f: RpmFacts) -> str:
        major = f.version.split(".")[0]
        if f.distribution == "Fedora" and major == "45" and f.manager == "dnf5":
            return "/usr/bin/dnf5"
        if (
            f.distribution in {"RedHat", "Rocky", "AlmaLinux"}
            and major == "9"
            and f.manager in {"dnf", "dnf4"}
        ):
            return "/usr/bin/dnf"
        raise _fail("package_provider_mismatch")

    async def _inventory(
        self, host: Host, runner: ModuleRunner, binary: str
    ) -> dict[str, str]:
        output, _ = await command(
            runner,
            host,
            (
                binary,
                "--quiet",
                "--cacheonly",
                "repoquery",
                "--upgrades",
                "--latest-limit=1",
                "--queryformat",
                "%{name}|%{arch}|%{evr}\\n",
            ),
            code="package_inventory_failed",
        )
        return rpm_rows(output)

    async def async_collect(
        self, host: Host, runner: ModuleRunner, *, refresh_cache: bool
    ) -> ExecutionResult:
        f = await facts(host, runner)
        binary = self._binary(f)
        await root(host, runner)
        if refresh_cache:
            await command(
                runner,
                host,
                (binary, "--assumeyes", "makecache", "--refresh"),
                code="package_metadata_failed",
            )
        names = await self._inventory(host, runner, binary)
        old = await installed(host, runner, tuple(sorted(names)[:MAX_PACKAGE_DETAILS]))
        return snapshot(f, names, old, None, self.scopes)

    async def async_apply(
        self, host: Host, selection: PackageSelection, runner: ModuleRunner
    ) -> ExecutionResult:
        f = await facts(host, runner)
        binary = self._binary(f)
        await root(host, runner)
        await command(
            runner,
            host,
            (binary, "--assumeyes", "makecache", "--refresh"),
            code="package_metadata_failed",
        )
        names = await self._inventory(host, runner, binary)
        validate_selection(selection, names)
        await command(
            runner,
            host,
            (
                binary,
                "--assumeyes",
                "upgrade",
                *(("--", *selection.names) if selection.names else ()),
            ),
            code="update_packages_failed",
            mutation=True,
        )
        return ExecutionResult(
            output="DNF update completed; review restart requirements manually."
        )


def validate_selection(selection: PackageSelection, names: dict[str, str]) -> None:
    if any(not _RPM_NAME.fullmatch(name) for name in selection.names):
        raise _fail("invalid_package_scope")
    if selection.names and not set(selection.names) <= set(names):
        raise _fail("package_selection_stale")


class ZypperProvider:
    legacy_key = "zypper"
    provider_id = "linux.zypper"
    scopes = _SCOPES
    _prefix = ("/usr/bin/zypper", "--non-interactive", "--no-cd")

    def classify_failure(self, default: str, output: str) -> str:
        return default

    def _scopes(self, f: RpmFacts) -> frozenset[UpdateScope]:
        if f.manager != "zypper":
            raise _fail("package_provider_mismatch")
        if f.distribution == "openSUSE Leap" and f.version.split(".")[:2] == [
            "16",
            "0",
        ]:
            return self.scopes
        if f.distribution == "openSUSE Tumbleweed":
            return frozenset()
        raise _fail("package_provider_mismatch")

    async def _inventory(self, host: Host, runner: ModuleRunner) -> dict[str, str]:
        output, _ = await command(
            runner,
            host,
            (
                *self._prefix,
                "--no-refresh",
                "--xmlout",
                "list-updates",
                "--type",
                "package",
            ),
            code="package_inventory_failed",
        )
        if "<!DOCTYPE" in output.upper() or "<!ENTITY" in output.upper():
            raise _fail("invalid_package_output")
        try:
            document = ET.fromstring(output)
        except ET.ParseError:
            raise _fail("invalid_package_output") from None
        if (
            document.tag != "stream"
            or document.find(".//update-list") is None
            or document.find(".//message[@type='error']") is not None
        ):
            raise _fail("invalid_package_output")
        names: dict[str, str] = {}
        for row in document.findall(".//update-list/update"):
            if row.get("kind") != "package":
                raise _fail("invalid_package_output")
            name, arch, version = (
                row.get("name", ""),
                row.get("arch", ""),
                row.get("edition", ""),
            )
            parsed = rpm_rows(name + "|" + arch + "|" + version)
            if set(parsed) & set(names):
                raise _fail("invalid_package_output")
            names.update(parsed)
        return names

    async def async_collect(
        self, host: Host, runner: ModuleRunner, *, refresh_cache: bool
    ) -> ExecutionResult:
        f = await facts(host, runner)
        scopes = self._scopes(f)
        await root(host, runner)
        if refresh_cache:
            await command(
                runner, host, (*self._prefix, "refresh"), code="package_metadata_failed"
            )
        names = await self._inventory(host, runner)
        old = await installed(host, runner, tuple(sorted(names)[:MAX_PACKAGE_DETAILS]))
        _, rc = await command(
            runner,
            host,
            (*self._prefix, "--no-refresh", "needs-rebooting"),
            code="package_reboot_probe_failed",
            accepted=None,
        )
        reboot = rc == 102 if rc in {0, 102} else None
        return snapshot(f, names, old, reboot, scopes)

    async def async_apply(
        self, host: Host, selection: PackageSelection, runner: ModuleRunner
    ) -> ExecutionResult:
        f = await facts(host, runner)
        if selection.scope not in self._scopes(f):
            raise _fail("package_scope_unsupported")
        await root(host, runner)
        await command(
            runner, host, (*self._prefix, "refresh"), code="package_metadata_failed"
        )
        names = await self._inventory(host, runner)
        validate_selection(selection, names)
        _, rc = await command(
            runner,
            host,
            (
                *self._prefix,
                "--no-refresh",
                "update",
                "--no-recommends",
                *(("--", *selection.names) if selection.names else ()),
            ),
            code="update_packages_failed",
            accepted=(0, 102, 103),
            mutation=True,
        )
        if rc == 103:
            raise _fail("package_manager_restart_required", rc)
        return ExecutionResult(
            output="Zypper package update completed.",
            reboot_required=True if rc == 102 else None,
        )
