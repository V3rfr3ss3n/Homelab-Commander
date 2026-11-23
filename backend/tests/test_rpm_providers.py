"""Manufactured RPM/native payloads only; every process boundary is injected."""

import json
from unittest.mock import AsyncMock

import pytest

from backend.homelab_backend.automation import AnsibleExecutor, AutomationExecutionError
from backend.homelab_backend.linux.providers.rpm import rpm_rows
from backend.homelab_backend.linux.providers.rpm_command import COMMAND_SCRIPT
from backend.homelab_backend.models import JobAction
from backend.tests.test_automation import _host


class RpmRunner:
    def __init__(self, distro="Fedora", version="45", manager="dnf5"):
        self.facts = {
            "ansible_distribution": distro,
            "ansible_distribution_version": version,
            "ansible_pkg_mgr": manager,
            "ansible_kernel": "synthetic",
        }
        self.pending = {"curl.x86_64": "0:2-1", "git.x86_64": "0:3-1"}
        self.writes = 0
        self.commands = []
        self.root = "0"
        self.fail = None
        self.update_rc = 0
        self.reboot_rc = 0
        self.raw_inventory = None

    async def async_module(
        self,
        host,
        module,
        arguments=None,
        *,
        become=False,
        failure_code="ansible_failed",
    ):
        if module == "ansible.builtin.setup":
            assert not become
            return {"ansible_facts": self.facts}, "private fixture facts"
        if module == "ansible.builtin.stat":
            assert json.loads(arguments)["path"] == "/usr/bin/flatpak"
            assert not become
            return {"stat": {"exists": False}}, ""
        assert module == "ansible.builtin.command"
        assert become
        argv = json.loads(arguments)["argv"]
        assert argv[:3] == ["/usr/bin/python3", "-c", COMMAND_SCRIPT]
        request = json.loads(argv[3])
        native = request["argv"]
        self.commands.append(native)
        assert native[0] in {
            "/usr/bin/id",
            "/usr/bin/rpm",
            "/usr/bin/dnf",
            "/usr/bin/dnf5",
            "/usr/bin/zypper",
        }
        assert not any(
            s in native
            for s in (
                "reboot",
                "install",
                "dist-upgrade",
                "--nogpgcheck",
                "--allowerasing",
                "--auto-import-keys",
            )
        )
        rc, output = 0, ""
        if self.fail and self.fail in native:
            rc, output = 7, "synthetic sensitive repository detail"
        elif native[0] == "/usr/bin/id":
            output = self.root
        elif "repoquery" in native:
            output = (
                self.raw_inventory
                if self.raw_inventory is not None
                else "\n".join(
                    name.rsplit(".", 1)[0] + "|x86_64|" + version
                    for name, version in self.pending.items()
                )
            )
        elif "list-updates" in native:
            output = (
                self.raw_inventory
                if self.raw_inventory is not None
                else "<stream><update-status><update-list>"
                + "".join(
                    f'<update kind="package" name="{name.rsplit(".", 1)[0]}" '
                    f'arch="x86_64" edition="{version}"/>'
                    for name, version in self.pending.items()
                )
                + "</update-list></update-status></stream>"
            )
        elif native[0] == "/usr/bin/rpm":
            output = "\n".join(
                name.rsplit(".", 1)[0] + "|x86_64|0:1-1"
                for name in native[native.index("--") + 1 :]
            )
        elif "needs-rebooting" in native:
            rc = self.reboot_rc
        elif "upgrade" in native or "update" in native:
            assert request["timeout"] == 3500
            self.writes += 1
            chosen = (
                native[native.index("--") + 1 :]
                if "--" in native
                else tuple(self.pending)
            )
            for name in chosen:
                self.pending.pop(name)
            rc = self.update_rc
        else:
            assert "makecache" in native or "refresh" in native
        return {
            "stdout": json.dumps({"rc": rc, "stdout": output})
        }, "never forward native output"


def executor(tmp_path, runner):
    result = AnsibleExecutor(tmp_path / "unused-key", tmp_path / "unused-hosts")
    result._async_module = runner.async_module
    return result


@pytest.mark.parametrize(
    ("distro", "version", "manager", "provider"),
    [
        ("Fedora", "45", "dnf5", "dnf"),
        ("RedHat", "9.6", "dnf", "dnf"),
        ("Rocky", "9.6", "dnf", "dnf"),
        ("AlmaLinux", "9.6", "dnf4", "dnf"),
        ("openSUSE Leap", "16.0", "zypper", "zypper"),
    ],
)
@pytest.mark.parametrize("scope", ["full", "single", "selected"])
async def test_native_scopes_measure_remaining_inventory_without_reboot(
    tmp_path, distro, version, manager, provider, scope
):
    runner = RpmRunner(distro, version, manager)
    run = executor(tmp_path, runner)
    host = _host().model_copy(update={"package_provider": provider})
    before = await run.async_execute(JobAction.CHECK_UPDATES, host)
    assert before.snapshot.updates == 2
    assert before.snapshot.security_updates is None
    assert all(p.is_security is None for p in before.snapshot.packages)
    assert before.snapshot.packages[0].old_version == "0:1-1"
    result = await run.async_execute(
        JobAction.UPDATE,
        host,
        "curl.x86_64" if scope == "single" else None,
        package_names=("curl.x86_64", "git.x86_64") if scope == "selected" else (),
    )
    assert runner.writes == 1
    assert result.snapshot.updates == (1 if scope == "single" else 0)
    assert len(result.snapshot.packages) == result.snapshot.updates
    assert result.snapshot.security_updates is None
    assert result.reboot_required is (False if provider == "zypper" else None)
    assert result.snapshot.package_scopes == ("full", "selected", "single")
    assert "private fixture" not in result.output
    assert "never forward" not in result.output


@pytest.mark.parametrize(
    ("distro", "version", "manager", "provider"),
    [
        ("Debian", "12", "apt", "dnf"),
        ("Fedora", "44", "dnf5", "dnf"),
        ("RedHat", "10", "dnf", "dnf"),
        ("Rocky", "9", "zypper", "dnf"),
        ("openSUSE Leap", "15.6", "zypper", "zypper"),
        ("openSUSE Leap", "16.0", "dnf", "zypper"),
    ],
)
async def test_wrong_family_version_manager_fails_before_root_or_metadata(
    tmp_path, distro, version, manager, provider
):
    runner = RpmRunner(distro, version, manager)
    with pytest.raises(AutomationExecutionError) as error:
        await executor(tmp_path, runner).async_execute(
            JobAction.UPDATE, _host().model_copy(update={"package_provider": provider})
        )
    assert error.value.code == "package_provider_mismatch"
    assert runner.commands == []
    assert runner.writes == 0


async def test_tumbleweed_is_read_only_and_rejects_update_before_any_command(tmp_path):
    runner = RpmRunner("openSUSE Tumbleweed", "20261118", "zypper")
    run = executor(tmp_path, runner)
    host = _host().model_copy(update={"package_provider": "zypper"})
    assert (
        await run.async_execute(JobAction.CHECK_UPDATES, host)
    ).snapshot.package_scopes == ()
    runner.commands.clear()
    with pytest.raises(AutomationExecutionError) as error:
        await run.async_execute(JobAction.UPDATE, host)
    assert error.value.code == "package_scope_unsupported"
    assert runner.commands == []


@pytest.mark.parametrize("provider", ["dnf", "zypper"])
async def test_missing_privilege_metadata_and_stale_selection_never_update(
    tmp_path, provider
):
    runner = (
        RpmRunner()
        if provider == "dnf"
        else RpmRunner("openSUSE Leap", "16.0", "zypper")
    )
    run, host = (
        executor(tmp_path, runner),
        _host().model_copy(update={"package_provider": provider}),
    )
    runner.root = "1000"
    with pytest.raises(AutomationExecutionError, match="sudo_unavailable"):
        await run.async_execute(JobAction.UPDATE, host)
    runner.root, runner.fail = "0", "makecache" if provider == "dnf" else "refresh"
    with pytest.raises(AutomationExecutionError, match="package_metadata_failed"):
        await run.async_execute(JobAction.UPDATE, host)
    runner.fail = None
    with pytest.raises(AutomationExecutionError, match="package_selection_stale"):
        await run.async_execute(JobAction.UPDATE, host, "missing.x86_64")
    with pytest.raises(AutomationExecutionError, match="invalid_package_scope"):
        await run.async_execute(JobAction.UPDATE, host, "curl:amd64")
    assert runner.writes == 0


@pytest.mark.parametrize(
    ("provider", "output"),
    [
        ("dnf", "broken output"),
        ("dnf", "bad;name|x86_64|1"),
        ("zypper", "<broken>"),
        (
            "zypper",
            '<stream><update-list><update kind="patch"/></update-list></stream>',
        ),
        ("zypper", "<!DOCTYPE stream><stream><update-list/></stream>"),
        ("zypper", "<stream/>"),
        ("zypper", '<stream><message type="error"/><update-list/></stream>'),
    ],
)
async def test_invalid_native_inventory_is_safe_failure(tmp_path, provider, output):
    runner = (
        RpmRunner()
        if provider == "dnf"
        else RpmRunner("openSUSE Leap", "16.0", "zypper")
    )
    runner.raw_inventory = output
    with pytest.raises(AutomationExecutionError) as error:
        await executor(tmp_path, runner).async_execute(
            JobAction.CHECK_UPDATES,
            _host().model_copy(update={"package_provider": provider}),
        )
    assert error.value.code == "invalid_package_output"
    assert error.value.output == ""
    assert runner.writes == 0


@pytest.mark.parametrize("rc", [102, 103, 1])
async def test_zypper_informational_codes_do_not_implicitly_retry(tmp_path, rc):
    runner = RpmRunner("openSUSE Leap", "16.0", "zypper")
    runner.update_rc = rc
    run, host = (
        executor(tmp_path, runner),
        _host().model_copy(update={"package_provider": "zypper"}),
    )
    if rc == 102:
        result = await run.async_execute(JobAction.UPDATE, host)
        assert result.reboot_required is True
        assert result.snapshot.reboot_required is True
    else:
        with pytest.raises(AutomationExecutionError) as error:
            await run.async_execute(JobAction.UPDATE, host)
        assert error.value.code == (
            "package_manager_restart_required"
            if rc == 103
            else "update_packages_failed"
        )
    assert runner.writes == 1


@pytest.mark.parametrize(
    ("rc", "expected"), [(0, False), (102, True), (104, None), (-1, None)]
)
async def test_zypper_reboot_signal_is_manager_specific(tmp_path, rc, expected):
    runner = RpmRunner("openSUSE Leap", "16.0", "zypper")
    runner.reboot_rc = rc
    result = await executor(tmp_path, runner).async_execute(
        JobAction.CHECK_UPDATES,
        _host().model_copy(update={"package_provider": "zypper"}),
    )
    assert result.snapshot.reboot_required is expected


def test_rpm_multiversion_rows_and_malformed_records():
    assert rpm_rows("kernel|x86_64|0:1-1\nkernel|x86_64|0:2-1") == {
        "kernel.x86_64": "0:1-1, 0:2-1"
    }
    for value in ("a|bad-arch|1", "a|x86_64|", "a|x86_64|" + "x" * 256):
        with pytest.raises(AutomationExecutionError, match="invalid_package_output"):
            rpm_rows(value)


@pytest.mark.parametrize(
    "result",
    [
        None,
        "invalid",
        '{"rc":true,"stdout":""}',
        '{"rc":0,"stdout":1}',
        "x" * 3_000_001,
    ],
)
async def test_wrapper_rejects_invalid_response_without_disclosure(result):
    from backend.homelab_backend.linux.providers.rpm import command

    runner = type(
        "Synthetic",
        (),
        {
            "async_module": AsyncMock(
                return_value=({"stdout": result}, "private output")
            )
        },
    )()
    with pytest.raises(
        AutomationExecutionError, match="invalid_package_output"
    ) as error:
        await command(runner, _host(), ("/usr/bin/id", "-u"), code="synthetic_failed")
    assert error.value.output == ""


async def test_wrapper_redacts_transport_errors_and_invalid_facts(tmp_path):
    from backend.homelab_backend.linux.providers.rpm import command, facts

    runner = type(
        "Synthetic",
        (),
        {
            "async_module": AsyncMock(
                side_effect=AutomationExecutionError(
                    "sudo_unavailable", "sensitive fixture"
                )
            )
        },
    )()
    for operation in (
        command(runner, _host(), ("/usr/bin/id", "-u"), code="synthetic_failed"),
        facts(_host(), runner),
    ):
        with pytest.raises(AutomationExecutionError) as error:
            await operation
        assert error.value.code == "sudo_unavailable"
        assert error.value.output == ""
    runner.async_module.side_effect = None
    for payload in (
        {},
        {"ansible_facts": {}},
        {"ansible_facts": {"ansible_distribution": 1}},
    ):
        runner.async_module.return_value = (payload, "untrusted")
        with pytest.raises(AutomationExecutionError, match="package_detection_failed"):
            await facts(_host(), runner)


@pytest.mark.parametrize(
    "mode", ["success", "missing", "timeout", "unicode", "oversized"]
)
def test_fixed_command_script_uses_argv_limits_and_safe_failures(
    monkeypatch, capsys, mode
):
    import io
    import selectors
    import subprocess
    import sys
    from types import SimpleNamespace

    class Process:
        def __init__(self, argv, *, stdin, stdout, stderr, env):
            assert argv == ["synthetic-command"]
            assert env["LC_ALL"] == env["LANG"] == "C"
            assert stdin == subprocess.DEVNULL
            assert stderr == subprocess.STDOUT
            assert stdout == subprocess.PIPE
            if mode == "missing":
                raise OSError("synthetic sensitive detail")
            self.stdout = io.BytesIO(
                b"\xff"
                if mode == "unicode"
                else b"x" * (2_097_153 if mode == "oversized" else 2)
            )
            self.returncode = None if mode == "timeout" else 0

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

        def wait(self, timeout=None):
            return self.returncode

    class Selector:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def register(self, file, event):
            self.file = file

        def unregister(self, file):
            self.file = None

        def get_map(self):
            return {1: self.file} if self.file else {}

        def select(self, timeout):
            if mode == "timeout":
                raise TimeoutError()
            return [(SimpleNamespace(fileobj=self.file), 1)]

    monkeypatch.setattr(subprocess, "Popen", Process)
    monkeypatch.setattr(selectors, "DefaultSelector", Selector)
    monkeypatch.setattr(
        sys,
        "argv",
        ["probe", json.dumps({"argv": ["synthetic-command"], "timeout": 180})],
    )
    exec(COMMAND_SCRIPT, {})
    result = json.loads(capsys.readouterr().out)
    assert result["rc"] == (
        0 if mode == "success" else -2 if mode == "oversized" else -1
    )
    assert result["stdout"] == ("xx" if mode == "success" else "")


@pytest.mark.parametrize("provider", ["dnf", "zypper"])
async def test_native_inventory_keeps_unbounded_total_and_bounded_details(
    tmp_path, provider
):
    runner = (
        RpmRunner()
        if provider == "dnf"
        else RpmRunner("openSUSE Leap", "16.0", "zypper")
    )
    runner.pending = {f"package-{i}.x86_64": "0:2-1" for i in range(60)}
    result = await executor(tmp_path, runner).async_execute(
        JobAction.CHECK_UPDATES,
        _host().model_copy(update={"package_provider": provider}),
    )
    assert result.snapshot.updates == 60
    assert result.snapshot.security_updates is None
    assert len(result.snapshot.packages) == 50
    assert all(p.is_security is None for p in result.snapshot.packages)
    rpm_call = next(args for args in runner.commands if args[0] == "/usr/bin/rpm")
    assert len(rpm_call[rpm_call.index("--") + 1 :]) == 50


@pytest.mark.parametrize("name", ["dnf", "zypper"])
async def test_native_capability_uses_v2_qualified_inventory_without_grants(name):
    from uuid import uuid4

    from backend.homelab_backend.contracts.resources import ResourceKind, ResourceRef
    from backend.homelab_backend.linux.capabilities import (
        PackageOperation,
        capability_binding,
    )
    from backend.homelab_backend.linux.evidence import (
        EvidenceState,
        InventoryEvidence,
        ObservedValue,
    )
    from backend.homelab_backend.linux.registry import PackageProviders

    binding = capability_binding(
        PackageProviders().resolve(name), PackageOperation.UPDATE
    )
    assert binding.definition.key.version.major == 2
    assert binding.definition.output_schema.id == "linux.inventory_evidence"
    inventory = InventoryEvidence(
        0,
        ObservedValue(EvidenceState.UNKNOWN, reason="linux.security_unverified"),
        ObservedValue(EvidenceState.UNKNOWN, reason="linux.reboot_unverified"),
    )
    assert binding.output_validator.validate(inventory) is inventory
    with pytest.raises(ValueError, match="qualified package inventory"):
        binding.output_validator.validate({"raw": "untrusted"})
    target = ResourceRef(ResourceKind.HOST, uuid4())
    assert (await binding.async_assess(target)).state.value == "unavailable"
    assert binding.input_validator.provider.provider_id == "linux." + name
    apt = capability_binding(
        PackageProviders().resolve("debian_apt"), PackageOperation.CHECK
    )
    assert apt.definition.key.version.major == 1


async def test_oversized_normalized_output_and_installed_mismatch_fail_closed():
    from backend.homelab_backend.linux.providers.rpm import command, facts, installed

    runner = type("Synthetic", (), {"async_module": AsyncMock()})()
    runner.async_module.return_value = (
        {"stdout": json.dumps({"rc": 0, "stdout": "x" * 2_097_153})},
        "ignored",
    )
    with pytest.raises(AutomationExecutionError, match="invalid_package_output"):
        await command(runner, _host(), ("/usr/bin/id", "-u"), code="synthetic_failed")
    runner.async_module.return_value = (
        {"stdout": json.dumps({"rc": 0, "stdout": "other|x86_64|1"})},
        "ignored",
    )
    with pytest.raises(AutomationExecutionError, match="package_selection_stale"):
        await installed(_host(), runner, ("curl.x86_64",))
    runner.async_module.return_value = (
        {
            "ansible_facts": {
                "ansible_distribution": "Fedora",
                "ansible_distribution_version": "45\nunsafe",
                "ansible_pkg_mgr": "dnf5",
            }
        },
        "ignored",
    )
    with pytest.raises(AutomationExecutionError, match="package_detection_failed"):
        await facts(_host(), runner)


@pytest.mark.parametrize("provider", ["dnf", "zypper"])
def test_non_apt_failures_do_not_reuse_apt_lock_categories(tmp_path, provider):
    from backend.homelab_backend.linux.ansible import AnsiblePackageTransport
    from backend.homelab_backend.linux.registry import PackageProviders

    transport = AnsiblePackageTransport(
        executor(tmp_path, RpmRunner()), PackageProviders()
    )
    host = _host().model_copy(update={"package_provider": provider})
    assert (
        transport.classify_failure(
            host, "package_metadata_failed", "Could not get lock"
        )
        == "package_metadata_failed"
    )


async def test_duplicate_native_xml_rows_are_not_counted_twice(tmp_path):
    runner = RpmRunner("openSUSE Leap", "16.0", "zypper")
    row = '<update kind="package" name="curl" arch="x86_64" edition="2"/>'
    runner.raw_inventory = (
        "<stream><update-list>" + row + row + "</update-list></stream>"
    )
    with pytest.raises(AutomationExecutionError, match="invalid_package_output"):
        await executor(tmp_path, runner).async_execute(
            JobAction.CHECK_UPDATES,
            _host().model_copy(update={"package_provider": "zypper"}),
        )
