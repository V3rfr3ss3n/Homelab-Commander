"""Native source dispatch uses manufactured host outputs; no real commands."""

import json
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from backend.homelab_backend.automation import AutomationExecutionError
from backend.homelab_backend.linux.domain import PackageSelection, UpdateScope
from backend.homelab_backend.linux.providers.flatpak import (
    FlatpakProvider,
    available,
    records,
)
from backend.homelab_backend.linux.registry import PackageProviders
from backend.homelab_backend.linux.sources import selections
from backend.homelab_backend.models import HostCreate, JobAction
from backend.tests.test_automation import _host
from backend.tests.test_rpm_providers import RpmRunner, executor

APP = "app/org.example.Editor/x86_64/stable"
RUNTIME = "runtime/org.example.Platform/x86_64/1"


class SourcesRunner(RpmRunner):
    def __init__(self, *, pacman=False, apt=False):
        super().__init__(
            "CachyOS" if pacman else "Fedora",
            "rolling" if pacman else "45",
            "pacman" if pacman else "dnf5",
        )
        if apt:
            self.facts.update(
                ansible_distribution="Debian",
                ansible_distribution_version="12",
                ansible_pkg_mgr="apt",
            )
        self.flatpak_present = True
        self.installed = {
            scope: {APP: "a" * 12, RUNTIME: "b" * 12} for scope in ("system", "user")
        }
        self.updates = {
            scope: {APP: "c" * 12, RUNTIME: "d" * 12} for scope in ("system", "user")
        }
        self.native_calls = []
        self.flatpak_fail = None
        self.bad_output = None
        self.privilege = []

    async def async_module(
        self,
        host,
        module,
        arguments=None,
        *,
        become=False,
        failure_code="ansible_failed",
    ):
        if self.facts["ansible_pkg_mgr"] == "apt":
            if module == "ansible.builtin.apt":
                assert become
                if arguments == "update_cache=true upgrade=dist":
                    self.pending.clear()
                    self.writes += 1
                return {}, ""
            if (
                module == "ansible.builtin.stat"
                and arguments == "path=/var/run/reboot-required"
            ):
                return {"stat": {"exists": False}}, ""
            if (
                module == "ansible.builtin.command"
                and json.loads(arguments)["argv"][0] == "/usr/bin/env"
            ):
                return {
                    "stdout": "Listing...\n"
                    + "\n".join(
                        name + "/stable-security 2 amd64 [upgradable from: 1]"
                        for name in self.pending
                    )
                }, ""
        if module == "ansible.builtin.stat":
            assert not become
            return {
                "stat": {
                    "exists": self.flatpak_present,
                    "isreg": True,
                    "executable": True,
                }
            }, ""
        if module == "ansible.builtin.command":
            argv = json.loads(arguments)["argv"]
            request = json.loads(argv[3])
            native = request["argv"]
            if native[0] == "/usr/bin/flatpak":
                self.native_calls.append(native)
                scope = "user" if "--user" in native else "system"
                self.privilege.append((scope, "update" in native, become))
                assert become == (scope == "system" and "update" in native)
                kind = "app" if "--app" in native else "runtime"
                if (
                    self.flatpak_fail
                    and "update" in native
                    and self.flatpak_fail == scope
                ):
                    return {
                        "stdout": json.dumps({
                            "rc": 1,
                            "stdout": "private synthetic output",
                        })
                    }, ""
                if "update" in native:
                    refs = [
                        value
                        for value in native
                        if value.startswith(("app/", "runtime/"))
                    ]
                    for ref in refs or list(self.updates[scope]):
                        self.installed[scope][ref] = self.updates[scope].pop(ref)
                    output = ""
                else:
                    is_list = "list" in native
                    data = self.installed[scope] if is_list else self.updates[scope]
                    output = "\n".join(
                        (ref.split("/", 1)[1] if is_list else ref)
                        + "\t"
                        + commit
                        + "\tsynthetic"
                        for ref, commit in data.items()
                        if ref.startswith(kind + "/")
                    )
                    if self.bad_output is not None:
                        output = self.bad_output
                return {
                    "stdout": json.dumps({"rc": 0, "stdout": output + "\n"})
                }, "private callback"
            if native[0] == "/usr/bin/checkupdates" or native[0] == "/usr/bin/pacman":
                self.native_calls.append(native)
                if "-Syu" in native:
                    assert become
                    self.pending.clear()
                    self.writes += 1
                    output, rc = "", 0
                else:
                    assert not become
                    output = "\n".join(name + " 1 -> 2" for name in self.pending)
                    rc = (
                        0
                        if output
                        else (2 if native[0].endswith("checkupdates") else 1)
                    )
                    if self.bad_output is not None:
                        output = self.bad_output
                return {"stdout": json.dumps({"rc": rc, "stdout": output})}, ""
        return await super().async_module(
            host, module, arguments, become=become, failure_code=failure_code
        )


def auto_host(**updates):
    return _host().model_copy(update={"package_provider": "auto", **updates})


async def test_auto_reads_three_sources_and_selected_dispatch_ignores_poisoned_cache(
    tmp_path,
):
    runner = SourcesRunner()
    run = executor(tmp_path, runner)
    host = auto_host()
    result = await run.async_execute(JobAction.CHECK_UPDATES, host)
    snapshot = result.snapshot
    assert snapshot.updates == 6
    assert [source.source for source in snapshot.package_observations] == [
        "dnf",
        "flatpak_system",
        "flatpak_user",
    ]
    assert snapshot.security_updates is None
    assert len({p.name for p in snapshot.packages}) == 6
    names = ("dnf::curl.x86_64", "flatpak_system::" + APP.replace("/", ":"))
    # No package map from host cache is used to authorize these actions.
    poisoned = host.model_copy(update={"packages": (), "updates": 999})
    updated = await run.async_execute(JobAction.UPDATE, poisoned, package_names=names)
    assert updated.snapshot.updates == 4
    assert "curl.x86_64" not in runner.pending
    assert APP not in runner.updates["system"]
    assert APP in runner.updates["user"]
    assert runner.writes == 1
    assert not updated.snapshot.reboot_required


@pytest.mark.parametrize("source", ["dnf", "flatpak_system", "flatpak_user"])
async def test_update_full_source_only(tmp_path, source):
    runner = SourcesRunner()
    result = await executor(tmp_path, runner).async_execute(
        JobAction.UPDATE, auto_host(), "source::" + source
    )
    assert result.snapshot.updates == 4
    counts = {
        item.source: item.updates for item in result.snapshot.package_observations
    }
    assert counts[source] == 0
    assert [count for key, count in counts.items() if key != source] == [2, 2]


async def test_full_host_update_serial_no_replay_and_read_after_native_change(tmp_path):
    runner = SourcesRunner()
    run = executor(tmp_path, runner)
    result = await run.async_execute(JobAction.UPDATE, auto_host())
    assert result.snapshot.updates == 0
    assert runner.writes == 1
    # A change outside Commander is reflected directly on the next native read.
    runner.updates["user"][APP] = "e" * 12
    changed = await run.async_execute(JobAction.CHECK_UPDATES, auto_host())
    assert changed.snapshot.updates == 1
    assert changed.snapshot.packages[0].source == "flatpak_user"


@pytest.mark.parametrize(
    "reference",
    [
        "curl.x86_64",
        "flatpak_system::app:org.example.Missing:x86_64:stable",
        "zypper::vim",
        "source::bogus",
        "dnf::--bad",
    ],
)
async def test_stale_forged_or_unqualified_selection_rejected_before_any_write(
    tmp_path, reference
):
    runner = SourcesRunner()
    with pytest.raises(AutomationExecutionError):
        await executor(tmp_path, runner).async_execute(
            JobAction.UPDATE, auto_host(), reference
        )
    assert runner.writes == 0
    assert not any("update" in call for call in runner.native_calls)


async def test_preflight_source_failure_prevents_first_write(tmp_path):
    runner = SourcesRunner()
    runner.bad_output = "invalid private output"
    with pytest.raises(AutomationExecutionError):
        await executor(tmp_path, runner).async_execute(JobAction.UPDATE, auto_host())
    assert runner.writes == 0
    assert not any("update" in call for call in runner.native_calls)


async def test_partial_source_failure_is_visible_no_second_write_retry(tmp_path):
    runner = SourcesRunner()
    runner.flatpak_fail = "system"
    with pytest.raises(AutomationExecutionError) as error:
        await executor(tmp_path, runner).async_execute(JobAction.UPDATE, auto_host())
    assert error.value.code == "package_sources_partial_failure"
    assert error.value.output == ""
    assert runner.writes == 1
    assert len([call for call in runner.native_calls if "update" in call]) == 1
    assert runner.updates["user"][APP] == "c" * 12


@pytest.mark.parametrize(
    "chosen", [("system",), ("flatpak_user",), ("flatpak_system", "flatpak_user")]
)
async def test_explicit_enabled_sources_and_per_user_privilege(tmp_path, chosen):
    runner = SourcesRunner()
    host = auto_host(package_sources=chosen)
    result = await executor(tmp_path, runner).async_execute(JobAction.UPDATE, host)
    assert len(result.snapshot.package_observations) == len(chosen)
    assert all(scope == "system" or not become for scope, _, become in runner.privilege)
    assert result.snapshot.reboot_required is None


async def test_missing_optional_flatpak_is_skipped_but_explicit_choice_fails(tmp_path):
    runner = SourcesRunner()
    runner.flatpak_present = False
    result = await executor(tmp_path, runner).async_execute(
        JobAction.CHECK_UPDATES, auto_host()
    )
    assert len(result.snapshot.package_observations) == 1
    with pytest.raises(AutomationExecutionError, match="package_source_unavailable"):
        await executor(tmp_path, runner).async_execute(
            JobAction.CHECK_UPDATES, auto_host(package_sources=("flatpak_user",))
        )


async def test_display_bound_interleaves_sources_and_keeps_full_counts(tmp_path):
    runner = SourcesRunner()
    runner.pending = {f"pkg{i:03}.x86_64": "2" for i in range(80)}
    result = await executor(tmp_path, runner).async_execute(
        JobAction.CHECK_UPDATES, auto_host()
    )
    assert result.snapshot.updates == 84
    assert len(result.snapshot.packages) == 50
    assert {p.source for p in result.snapshot.packages} == {
        "dnf",
        "flatpak_system",
        "flatpak_user",
    }


async def test_pacman_flatpak_independent_scopes_full_and_external_read(tmp_path):
    runner = SourcesRunner(pacman=True)
    run = executor(tmp_path, runner)
    checked = await run.async_execute(JobAction.CHECK_UPDATES, auto_host())
    assert checked.snapshot.updates == 6
    row = next(p for p in checked.snapshot.packages if p.source == "pacman")
    assert row.scopes == ("full",)
    with pytest.raises(AutomationExecutionError, match="package_scope_unsupported"):
        await run.async_execute(JobAction.UPDATE, auto_host(), row.name)
    assert runner.writes == 0
    updated = await run.async_execute(JobAction.UPDATE, auto_host(), "source::pacman")
    assert updated.snapshot.updates == 4
    assert all("-Sy" not in call for call in runner.native_calls)
    assert sum("-Syu" in call for call in runner.native_calls) == 1


@pytest.mark.parametrize(
    "output",
    [
        "bad",
        "app/ID/x/stable\tbad\tsynthetic",
        "runtime/ID/x/stable\t" + "a" * 12 + "\tsynthetic",
        "app/ID/x/--bad\t" + "a" * 12 + "\tsynthetic",
    ],
)
def test_flatpak_native_parser_rejects_malformed_or_wrong_kind(output):
    with pytest.raises(AutomationExecutionError, match="invalid_package_output"):
        records(output, "app")


def test_flatpak_short_commits_partial_refs_and_duplicates():
    output = APP.split("/", 1)[1] + "\t" + "a" * 12 + "\tsynthetic"
    assert records(output, "app") == {(APP, "synthetic"): "a" * 12}
    with pytest.raises(AutomationExecutionError):
        records(output + "\n" + output, "app")
    assert FlatpakProvider("user").classify_failure("safe", "private") == "safe"


@pytest.mark.parametrize(
    "stat",
    [
        {},
        {"stat": {}},
        {"stat": {"exists": True, "isreg": False}},
        {"stat": {"exists": True, "isreg": True, "executable": False}},
    ],
)
async def test_binary_detection_requires_valid_executable(stat):
    runner = AsyncMock()
    runner.async_module.return_value = (stat, "private")
    with pytest.raises(AutomationExecutionError):
        await available(_host(), runner)


def test_source_choices_and_target_scopes_are_typed_and_canonical():
    args = {
        "name": "Synthetic",
        "address": "node-01.example.invalid",
        "username": "automation",
    }
    assert HostCreate(
        **args, package_sources=("system", "flatpak_user")
    ).package_sources == ("flatpak_user", "system")
    for invalid in [(), ("system", "system"), ("other",)]:
        with pytest.raises(ValidationError):
            HostCreate(**args, package_sources=invalid)
    with pytest.raises(AutomationExecutionError):
        selections(
            PackageSelection(UpdateScope.SELECTED, ("source::dnf", "dnf::curl")),
            frozenset({"dnf"}),
        )
    assert PackageProviders().resolve("pacman").scopes == frozenset({UpdateScope.FULL})


async def test_empty_native_flatpak_installations_do_not_query_remote_catalogs(
    tmp_path,
):
    runner = SourcesRunner()
    runner.installed = {scope: {} for scope in ("system", "user")}
    runner.updates = {scope: {} for scope in ("system", "user")}
    result = await executor(tmp_path, runner).async_execute(
        JobAction.CHECK_UPDATES, auto_host()
    )
    assert result.snapshot.updates == 2
    assert not any("remote-ls" in call for call in runner.native_calls)
    assert [source.updates for source in result.snapshot.package_observations] == [
        2,
        0,
        0,
    ]


async def test_zypper_source_retains_native_restart_hint(tmp_path):
    runner = SourcesRunner()
    runner.facts.update(
        ansible_distribution="openSUSE Leap",
        ansible_distribution_version="16.0",
        ansible_pkg_mgr="zypper",
    )
    runner.update_rc = 102
    result = await executor(tmp_path, runner).async_execute(
        JobAction.UPDATE, auto_host(), "source::zypper"
    )
    assert result.snapshot.reboot_required is True
    assert result.snapshot.updates == 4


async def test_unsupported_pacman_host_never_reaches_native_commands(tmp_path):
    runner = SourcesRunner(pacman=True)
    runner.facts["ansible_distribution"] = "Other"
    with pytest.raises(AutomationExecutionError, match="package_provider_mismatch"):
        await executor(tmp_path, runner).async_execute(JobAction.UPDATE, auto_host())
    assert not runner.native_calls
    assert runner.writes == 0


async def test_known_apt_security_evidence_survives_unknown_flatpak_classification(
    tmp_path,
):
    runner = SourcesRunner(apt=True)
    result = await executor(tmp_path, runner).async_execute(
        JobAction.CHECK_UPDATES, auto_host()
    )
    assert result.snapshot.security_updates is None
    assert result.snapshot.package_observations[0].security_updates == 2
    assert all(
        s.security_updates is None for s in result.snapshot.package_observations[1:]
    )


def test_empty_persisted_source_setting_cannot_expand_to_automatic_sources():
    from backend.homelab_backend.models import Host

    data = _host().model_dump()
    data["package_sources"] = []
    with pytest.raises(ValidationError):
        Host.model_validate(data)


def test_empty_native_flatpak_table_with_newline_is_a_valid_zero():
    assert records("\n", "app") == {}
    assert records("\n\n", "runtime") == {}
