"""System-manager discovery uses injected facts and never probes by mutation."""

import json
from unittest.mock import AsyncMock

import pytest

from backend.homelab_backend.automation import AutomationExecutionError
from backend.homelab_backend.linux.registry import PackageProviders
from backend.homelab_backend.models import HostCreate, JobAction
from backend.tests.test_automation import _host
from backend.tests.test_rpm_providers import RpmRunner, executor


@pytest.mark.parametrize(
    ("distro", "version", "manager"),
    [
        ("Fedora", "45", "dnf5"),
        ("Rocky", "9.6", "dnf"),
        ("openSUSE Leap", "16.0", "zypper"),
    ],
)
async def test_auto_discovers_checks_and_updates_one_package(
    tmp_path, distro, version, manager
):
    runner = RpmRunner(distro, version, manager)
    host = _host().model_copy(update={"package_provider": "auto"})
    run = executor(tmp_path, runner)
    checked = await run.async_execute(JobAction.CHECK_UPDATES, host)
    assert checked.snapshot.updates == 2
    assert checked.snapshot.security_updates is None
    updated = await run.async_execute(
        JobAction.UPDATE,
        host,
        ("zypper" if manager == "zypper" else "dnf") + "::curl.x86_64",
    )
    assert updated.snapshot.updates == 1
    assert updated.snapshot.packages[0].display_name == "git.x86_64"
    assert runner.writes == 1
    assert host.package_provider == "auto"


@pytest.mark.parametrize(
    ("distro", "version", "manager", "code"),
    [
        ("Other", "1", "apt", "package_provider_unsupported"),
        ("Alpine", "3.22", "apk", "package_provider_mismatch"),
        ("Fedora", "44", "dnf5", "package_provider_mismatch"),
        ("Debian", "12", "zypper", "package_provider_mismatch"),
    ],
)
async def test_unknown_or_mismatched_detection_never_writes(
    tmp_path, distro, version, manager, code
):
    runner = RpmRunner(distro, version, manager)
    with pytest.raises(AutomationExecutionError) as error:
        await executor(tmp_path, runner).async_execute(
            JobAction.UPDATE, _host().model_copy(update={"package_provider": "auto"})
        )
    assert error.value.code == code
    assert runner.writes == 0
    assert runner.commands == []


async def test_auto_tumbleweed_remains_readonly(tmp_path):
    runner = RpmRunner("openSUSE Tumbleweed", "20261118", "zypper")
    run = executor(tmp_path, runner)
    host = _host().model_copy(update={"package_provider": "auto"})
    checked = await run.async_execute(JobAction.CHECK_UPDATES, host)
    assert checked.snapshot.package_scopes == ()
    with pytest.raises(AutomationExecutionError):
        await run.async_execute(JobAction.UPDATE, host)
    assert runner.writes == 0


@pytest.mark.parametrize("distro", ["Debian", "Ubuntu"])
async def test_auto_apt_returns_observed_scopes_and_no_extra_mutation(tmp_path, distro):
    run = executor(tmp_path, RpmRunner())
    facts = {
        "ansible_facts": {
            "ansible_distribution": distro,
            "ansible_distribution_version": "12",
            "ansible_pkg_mgr": "apt",
            "ansible_kernel": "synthetic",
        }
    }
    calls = []

    def run_module(host, name, arguments=None, **kwargs):
        calls.append((name, arguments, kwargs))
        if name == "ansible.builtin.setup":
            return facts, ""
        if name == "ansible.builtin.stat":
            return {"stat": {"exists": False}}, ""
        if name == "ansible.builtin.command":
            assert json.loads(arguments)["argv"][-2:] == ["list", "--upgradable"]
            return {"stdout": "Listing...\n"}, ""
        assert name == "ansible.builtin.apt"
        return {}, ""

    run._async_module = AsyncMock(side_effect=run_module)
    host = _host().model_copy(update={"package_provider": "auto"})
    checked = await run.async_execute(JobAction.CHECK_UPDATES, host)
    assert checked.snapshot.package_scopes == ("full", "selected", "single")
    assert checked.snapshot.security_updates == 0
    assert not checked.snapshot.reboot_required
    calls.clear()
    await run.async_execute(JobAction.UPDATE, host)
    assert (
        sum(
            name == "ansible.builtin.apt"
            and arguments == "update_cache=true upgrade=dist"
            for name, arguments, _ in calls
        )
        == 1
    )


async def test_detection_failure_is_safe(tmp_path):
    run = executor(tmp_path, RpmRunner())
    run._async_module = AsyncMock(return_value=({"ansible_facts": None}, "private"))
    with pytest.raises(AutomationExecutionError) as error:
        await run.async_execute(
            JobAction.CHECK_UPDATES,
            _host().model_copy(update={"package_provider": "auto"}),
        )
    assert error.value.code == "package_detection_failed"
    assert error.value.output == ""


def test_default_and_explicit_configuration():
    args = {
        "name": "Synthetic",
        "address": "node-01.example.invalid",
        "username": "automation",
    }
    assert HostCreate(**args).package_provider == "debian_apt"
    assert HostCreate(**args, package_provider="auto").package_provider == "auto"
    assert (
        HostCreate(**args, package_provider="debian_apt").package_provider
        == "debian_apt"
    )
    assert PackageProviders().resolve("auto").provider_id == "linux.auto"
    assert (
        PackageProviders().resolve("auto").classify_failure("safe", "private") == "safe"
    )
