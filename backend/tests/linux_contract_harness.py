"""Reusable provider cases with manufactured outputs; never run package commands."""

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.homelab_backend.automation import AnsibleExecutor, ExecutionResult
from backend.homelab_backend.execution.results import AutomationExecutionError
from backend.homelab_backend.linux.domain import UpdateScope
from backend.homelab_backend.linux.ports import PackageProvider
from backend.homelab_backend.linux.providers.apt import DebianAptProvider
from backend.homelab_backend.linux.registry import PackageProviders
from backend.homelab_backend.models import JobAction
from backend.tests.test_automation import _host
from backend.tests.test_linux_boundary import SyntheticPackages


@dataclass(frozen=True)
class InventoryCase:
    text: str
    total: int
    security: int
    names: tuple[str, ...]


@dataclass(frozen=True)
class ProviderCase:
    provider: PackageProvider
    before: InventoryCase
    after: tuple[tuple[UpdateScope, InventoryCase], ...]


_APT_ROWS = (
    "curl/stable-security 2 amd64 [upgradable from: 1]",
    "git/stable 4 amd64 [upgradable from: 3]",
    "openssl/stable 6 amd64 [upgradable from: 5]",
)
PROVIDER_CASES = (
    ProviderCase(
        DebianAptProvider(),
        InventoryCase("\n".join(_APT_ROWS), 3, 1, ("curl", "git", "openssl")),
        (
            (UpdateScope.FULL, InventoryCase("Listing...", 0, 0, ())),
            (
                UpdateScope.SINGLE,
                InventoryCase("\n".join(_APT_ROWS[1:]), 2, 0, ("git", "openssl")),
            ),
            (UpdateScope.SELECTED, InventoryCase(_APT_ROWS[2], 1, 0, ("openssl",))),
        ),
    ),
    ProviderCase(
        SyntheticPackages(),
        InventoryCase("one|1|2|1\ntwo|3|4|0", 2, 1, ("one", "two")),
        ((UpdateScope.FULL, InventoryCase("", 0, 0, ())),),
    ),
)


def assert_inventory(result: ExecutionResult, expected: InventoryCase) -> None:
    assert result.snapshot is not None
    assert result.snapshot.updates == expected.total
    assert result.snapshot.security_updates == expected.security
    assert tuple(p.name for p in result.snapshot.packages) == expected.names
    assert result.snapshot.checked_at.tzinfo is not None


async def exercise_scope(
    case: ProviderCase, scope: UpdateScope, tmp_path: Path
) -> None:
    """The same runner/transport/application path must obey every provider scope."""
    provider = case.provider
    executor = AnsibleExecutor(
        tmp_path / "unused-key",
        tmp_path / "unused-hosts",
        package_providers=PackageProviders((provider,)),
    )
    module = AsyncMock(
        side_effect=[
            ({"ansible_facts": {}}, "facts"),
            ({}, "cache"),
            ({"stdout": case.before.text}, "list"),
            ({"stat": {"exists": False}}, "restart"),
        ]
    )
    executor._async_module = module
    host = _host().model_copy(update={"package_provider": provider.legacy_key})
    assert_inventory(
        await executor.async_execute(JobAction.CHECK_UPDATES, host), case.before
    )
    assert module.await_count == 4
    module.reset_mock()
    if scope not in provider.scopes:
        module.side_effect = AssertionError("Unsupported scope must not reach runner")
        with pytest.raises(AutomationExecutionError) as error:
            await executor.async_execute(
                JobAction.UPDATE,
                host,
                "curl" if scope is UpdateScope.SINGLE else None,
                package_names=("curl", "git") if scope is UpdateScope.SELECTED else (),
            )
        assert error.value.code == "package_scope_unsupported"
        module.assert_not_awaited()
        return
    expected = dict(case.after)[scope]
    module.side_effect = [
        ({}, "update"),
        ({"ansible_facts": {}}, "facts"),
        ({"stdout": expected.text}, "list"),
        ({"stat": {"exists": True}}, "restart"),
    ]
    result = await executor.async_execute(
        JobAction.UPDATE,
        host,
        "curl" if scope is UpdateScope.SINGLE else None,
        package_names=("curl", "git") if scope is UpdateScope.SELECTED else (),
    )
    assert_inventory(result, expected)
    assert result.reboot_required is True
    assert module.await_count == 4
    # Exactly one privileged mutation, then fresh status; no second refresh/reboot.
    assert module.await_args_list[0].kwargs["become"] is True
    assert all(not c.kwargs.get("become", False) for c in module.await_args_list[1:])
    assert not any(
        c.args[1] == "ansible.builtin.reboot" for c in module.await_args_list
    )
