"""Linux boundary proof: all modules/providers below are synthetic, no host I/O."""

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.homelab_backend.app import create_app
from backend.homelab_backend.automation import AnsibleExecutor, AutomationExecutionError
from backend.homelab_backend.config import Settings
from backend.homelab_backend.contracts.capabilities import (
    CapabilityState,
    RecoveryMode,
    RiskClass,
)
from backend.homelab_backend.contracts.providers import CapabilityProvider
from backend.homelab_backend.contracts.resources import ResourceKind, ResourceRef
from backend.homelab_backend.linux.ansible import AnsiblePackageTransport
from backend.homelab_backend.linux.application import LinuxPackages
from backend.homelab_backend.linux.capabilities import (
    PackageCapability,
    PackageOperation,
    PackageRequest,
)
from backend.homelab_backend.linux.domain import (
    PackageSelection,
    PackageStatus,
    UpdateScope,
)
from backend.homelab_backend.linux.ports import PackageProvider
from backend.homelab_backend.linux.providers.apt import DebianAptProvider
from backend.homelab_backend.linux.registry import PackageProviders
from backend.homelab_backend.models import (
    MAX_PACKAGE_DETAILS,
    Host,
    JobAction,
    PackageInfo,
)
from backend.tests.test_automation import _host
from backend.tests.test_backend_api import AUTH, TOKEN, _terminal_job


class SyntheticPackages:
    """Independent full-only contract fixture, never registered in production."""

    legacy_key = "synthetic_packages"
    provider_id = "synthetic.packages"
    scopes = frozenset({UpdateScope.FULL})
    cache_failure_code = "synthetic_cache_failed"
    reboot_probe = ("synthetic.stat", "synthetic-restart-flag")
    update_module = ("synthetic.packages", "apply-all")
    cache_refresh_module = ("synthetic.packages", "refresh")
    list_command = ("synthetic-package-list",)

    def single_update_module(self, _name: str) -> tuple[str, str]:
        raise AssertionError("Unsupported selection must fail before command creation")

    def selected_update_module(self, _names: tuple[str, ...]) -> tuple[str, str]:
        raise AssertionError("Unsupported selection must fail before command creation")

    def classify_failure(self, default: str, output: str) -> str:
        return "synthetic_locked" if output == "busy" else default

    def parse_updates(self, output: str, *, reboot_required: bool) -> PackageStatus:
        packages = []
        for line in output.splitlines():
            name, old, new, security = line.split("|")
            if security not in {"0", "1"}:
                raise ValueError("Invalid synthetic status")
            packages.append(
                PackageInfo(
                    name=name,
                    old_version=old,
                    new_version=new,
                    is_security=security == "1",
                )
            )
        return PackageStatus(
            len(packages),
            sum(p.is_security for p in packages),
            reboot_required,
            tuple(packages[:MAX_PACKAGE_DETAILS]),
        )


class SyntheticRunner:
    """Respond only to a fixed fixture vocabulary; cannot start a subprocess."""

    def __init__(self) -> None:
        self.updated = False
        self.calls: list[tuple[str, str | None, bool, str]] = []

    async def async_module(
        self,
        host: Host,
        module: str,
        arguments: str | None = None,
        *,
        become: bool = False,
        failure_code: str = "ansible_failed",
    ) -> tuple[dict[str, object], str]:
        assert host.package_provider == "synthetic_packages"
        self.calls.append((module, arguments, become, failure_code))
        if module == "ansible.builtin.setup":
            return {"ansible_facts": {"ansible_distribution": "Synthetic"}}, "facts"
        if module == "synthetic.packages":
            assert become
            if arguments == "apply-all":
                self.updated = True
            else:
                assert arguments == "refresh"
            return {}, "synthetic cache/update"
        if module == "ansible.builtin.command":
            assert json.loads(arguments) == {"argv": ["synthetic-package-list"]}
            return {"stdout": "" if self.updated else "one|1|2|1\ntwo|3|4|0"}, "list"
        assert module == "synthetic.stat"
        assert arguments == "synthetic-restart-flag"
        return {"stat": {"exists": self.updated}}, "restart status"


def _executor(tmp_path: Path) -> tuple[AnsibleExecutor, SyntheticRunner]:
    executor = AnsibleExecutor(
        tmp_path / "unused-key",
        tmp_path / "unused-known-hosts",
        package_providers=PackageProviders((SyntheticPackages(),)),
    )
    runner = SyntheticRunner()
    executor.async_module = runner.async_module
    # A missed transport injection must fail, never fall through to SSH.
    executor._async_module = AsyncMock(
        side_effect=AssertionError("Real runner forbidden")
    )
    return executor, runner


def test_provider_registry_and_selections_are_bounded() -> None:
    assert isinstance(PackageProviders().resolve("debian_apt"), DebianAptProvider)
    with pytest.raises(ValueError, match="unsupported"):
        PackageProviders().resolve("synthetic_packages")
    with pytest.raises(ValueError, match="duplicate"):
        PackageProviders((DebianAptProvider(), DebianAptProvider()))
    for key, provider_id in (("INVALID", "synthetic.valid"), ("valid", "invalid")):
        provider = SyntheticPackages()
        provider.legacy_key, provider.provider_id = key, provider_id
        with pytest.raises(ValueError, match="registration"):
            PackageProviders((provider,))
    assert PackageSelection.from_legacy(None, ("vim", "curl")).names == ("curl", "vim")
    assert PackageSelection.from_legacy("vim", ()).scope is UpdateScope.SINGLE
    assert PackageSelection.from_legacy(None, ()).scope is UpdateScope.FULL
    with pytest.raises(ValueError, match="exclusive"):
        PackageSelection.from_legacy("vim", ("curl",))
    for scope, names in (
        (UpdateScope.FULL, ("vim",)),
        (UpdateScope.SINGLE, ()),
        (UpdateScope.SELECTED, ()),
        (UpdateScope.SELECTED, ("vim", "vim")),
        (UpdateScope.SINGLE, ("vim;reboot",)),
        (UpdateScope.SINGLE, ("a" * 256,)),
        (UpdateScope.SELECTED, tuple(f"p-{i}" for i in range(MAX_PACKAGE_DETAILS + 1))),
    ):
        with pytest.raises(ValueError, match="scope"):
            PackageSelection(scope, names)


@pytest.mark.parametrize("provider", [DebianAptProvider(), SyntheticPackages()])
@pytest.mark.parametrize("operation", list(PackageOperation))
async def test_both_providers_bind_shared_versioned_capabilities(
    provider: PackageProvider, operation: PackageOperation
) -> None:
    binding: CapabilityProvider[PackageRequest, PackageStatus] = PackageCapability(
        provider, operation
    )
    assert binding.provider_id == provider.provider_id
    definition = binding.definition
    assert definition.key.id == operation.value
    assert definition.key.version.major == 1
    assert definition.input_schema.id == "linux.package_request"
    assert definition.output_schema.id == "linux.package_status"
    update = operation is PackageOperation.UPDATE
    assert definition.risk is (RiskClass.MUTATING if update else RiskClass.READ_ONLY)
    assert definition.recovery is (
        RecoveryMode.NEVER_REPLAY if update else RecoveryMode.RETRY_READ
    )
    request = PackageRequest(operation, PackageSelection() if update else None)
    assert binding.input_validator.validate(request) == request
    status = PackageStatus(0, 0, False)
    assert binding.output_validator.validate(status) == status
    for invalid in ({"raw": "untrusted"}, None):
        with pytest.raises(ValueError, match="request"):
            binding.input_validator.validate(invalid)
        with pytest.raises(ValueError, match="status"):
            binding.output_validator.validate(invalid)
    other = PackageOperation.CHECK if update else PackageOperation.UPDATE
    with pytest.raises(ValueError, match="request"):
        binding.input_validator.validate(
            PackageRequest(other, None if update else PackageSelection())
        )
    target = ResourceRef(ResourceKind.HOST, uuid4())
    assessment = await binding.async_assess(target)
    assert assessment.state is CapabilityState.UNAVAILABLE
    assert assessment.reason_codes == ("linux.readiness_unknown",)
    service = ResourceRef(ResourceKind.MANAGED_SERVICE, uuid4())
    assert (await binding.async_assess(service)).state is CapabilityState.UNSUPPORTED
    # Assessing support has no transport or execution reference to invoke.


def test_request_and_status_validation_preserve_count_invariants() -> None:
    with pytest.raises(ValueError, match="request scope"):
        PackageRequest(PackageOperation.UPDATE)
    with pytest.raises(ValueError, match="request scope"):
        PackageRequest(PackageOperation.CHECK, PackageSelection())
    binding = PackageCapability(SyntheticPackages(), PackageOperation.UPDATE)
    with pytest.raises(ValueError, match="unsupported"):
        binding.input_validator.validate(
            PackageRequest(
                PackageOperation.UPDATE, PackageSelection(UpdateScope.SINGLE, ("vim",))
            )
        )
    for updates, security, packages in (
        (0, 1, ()),
        (0, 0, (PackageInfo(name="vim", old_version="1", new_version="2"),)),
        (
            1,
            0,
            (
                PackageInfo(
                    name="vim", old_version="1", new_version="2", is_security=True
                ),
            ),
        ),
    ):
        with pytest.raises(ValueError, match="counts"):
            PackageStatus(updates, security, False, packages)
    for provider in (DebianAptProvider(), SyntheticPackages()):
        output = "\n".join(
            f"p-{i}/stable-security 2 amd64 [upgradable from: 1]"
            if isinstance(provider, DebianAptProvider)
            else f"p-{i}|1|2|1"
            for i in range(60)
        )
        status = provider.parse_updates(output, reboot_required=False)
        assert status.updates == status.security_updates == 60
        assert len(status.packages) == MAX_PACKAGE_DETAILS


@pytest.mark.parametrize("scope", [UpdateScope.SINGLE, UpdateScope.SELECTED])
async def test_unsupported_scope_fails_before_transport(
    tmp_path: Path, scope: UpdateScope
) -> None:
    executor, runner = _executor(tmp_path)
    host = _host().model_copy(update={"package_provider": "synthetic_packages"})
    with pytest.raises(AutomationExecutionError) as error:
        await executor.async_execute(
            JobAction.UPDATE,
            host,
            "vim" if scope is UpdateScope.SINGLE else None,
            package_names=("vim", "curl") if scope is UpdateScope.SELECTED else (),
        )
    assert error.value.code == "package_scope_unsupported"
    assert runner.calls == []
    assert not runner.updated
    with pytest.raises(AutomationExecutionError) as error:
        await executor.async_execute(JobAction.UPDATE, host, "bad;command")
    assert error.value.code == "invalid_package_scope"
    assert runner.calls == []


async def test_provider_boundary_rejects_unknown_and_malformed_output(
    tmp_path: Path,
) -> None:
    runner = SyntheticRunner()
    registry = PackageProviders((SyntheticPackages(),))
    transport = AnsiblePackageTransport(runner, registry)
    service = LinuxPackages(transport, registry)
    with pytest.raises(ValueError, match="unsupported"):
        await service.async_check(_host())
    assert runner.calls == []
    host = _host().model_copy(update={"package_provider": "synthetic_packages"})
    assert transport.classify_failure(host, "fallback", "busy") == "synthetic_locked"
    assert transport.classify_failure(host, "fallback", "other") == "fallback"
    assert transport.classify_failure(_host(), "fallback", "busy") == "fallback"
    transport.async_packages = AsyncMock(
        return_value=replace(
            await transport.async_packages(
                host, registry.resolve(host.package_provider)
            ),
            value="malformed|sensitive-untrusted-fixture",
        )
    )
    with pytest.raises(AutomationExecutionError) as error:
        await service.async_check(host)
    assert error.value.code == "invalid_package_output"
    assert error.value.output == ""
    assert "sensitive" not in str(error.value)


def test_second_provider_uses_existing_api_worker_policy_and_persistence(
    tmp_path: Path,
) -> None:
    executor, runner = _executor(tmp_path)
    with TestClient(
        create_app(Settings(data_dir=tmp_path, api_token=TOKEN), executor=executor)
    ) as client:
        response = client.post(
            "/api/v1/hosts",
            headers=AUTH,
            json={
                "name": "Synthetic node",
                "address": "node-01.example.invalid",
                "username": "automation",
                "package_provider": "synthetic_packages",
            },
        )
        assert response.status_code == 201
        host_id = response.json()["id"]
        check = client.post(
            f"/api/v1/hosts/{host_id}/actions/check-updates", headers=AUTH
        )
        assert check.status_code == 202
        assert _terminal_job(client, check.json()["id"])["state"] == "success"
        before = client.get(f"/api/v1/hosts/{host_id}", headers=AUTH).json()
        assert before["updates"] == 2
        assert before["security_updates"] == 1
        calls = len(runner.calls)
        denied = client.post(
            f"/api/v1/hosts/{host_id}/actions/update",
            json={"package_name": "one"},
            headers=AUTH,
        )
        assert denied.status_code == 202
        failed = _terminal_job(client, denied.json()["id"])
        assert failed["state"] == "failed"
        assert failed["error_code"] == "package_scope_unsupported"
        assert len(runner.calls) == calls
        assert (
            client.get(f"/api/v1/hosts/{host_id}", headers=AUTH).json()["updates"] == 2
        )
        # Authentication cannot be replaced by a provider's technical support.
        assert client.post(f"/api/v1/hosts/{host_id}/actions/update").status_code == 401
        update = client.post(f"/api/v1/hosts/{host_id}/actions/update", headers=AUTH)
        assert update.status_code == 202
        job = _terminal_job(client, update.json()["id"])
        assert job["state"] == "success"
        assert job["execution"]["scope"]["operation"] == "linux.update"
        after = client.get(f"/api/v1/hosts/{host_id}", headers=AUTH).json()
        assert after["id"] == host_id
        assert after["package_provider"] == "synthetic_packages"
        assert after["updates"] == after["security_updates"] == 0
        assert after["reboot_required"]
        packages = client.get(f"/api/v1/hosts/{host_id}/packages", headers=AUTH).json()
        assert packages["total"] == 0
        assert packages["packages"] == []
        assert sum(call[1] == "apply-all" for call in runner.calls) == 1
        assert not any("reboot" in call[0] for call in runner.calls)


def test_untrusted_scope_and_registration_values_fail_safely() -> None:
    for scope, names in (
        ("full", ()),
        (UpdateScope.SINGLE, ["vim"]),
        (UpdateScope.SINGLE, (None,)),
    ):
        with pytest.raises(ValueError, match="scope"):
            PackageSelection(scope, names)
    for operation, selection in (
        ("linux.check_updates", None),
        (PackageOperation.UPDATE, {"scope": "full"}),
    ):
        with pytest.raises(ValueError, match="request scope"):
            PackageRequest(operation, selection)
    second = SyntheticPackages()
    second.legacy_key = "other_synthetic"
    with pytest.raises(ValueError, match="registration"):
        PackageProviders((SyntheticPackages(), second))
    with pytest.raises(ValueError, match="unsupported"):
        PackageProviders(()).resolve("debian_apt")
    rows = tuple(
        PackageInfo(name=f"p-{i}", old_version="1", new_version="2")
        for i in range(MAX_PACKAGE_DETAILS + 1)
    )
    with pytest.raises(ValueError, match="counts"):
        PackageStatus(len(rows), 0, False, rows)
