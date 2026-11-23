"""Disposable preview reflects native-source changes without real execution."""

import pytest

from backend.homelab_backend.automation import AutomationExecutionError
from backend.homelab_backend.models import JobAction
from backend.homelab_backend.preview import PreviewExecutor
from backend.tests.test_package_sources import auto_host


@pytest.mark.parametrize("provider", ["auto", "debian_apt", "dnf", "pacman", "zypper"])
async def test_preview_source_single_full_and_filter_reset_keep_native_progress(
    provider,
):
    executor = PreviewExecutor()
    host = auto_host(
        package_provider=provider,
        package_sources=("system", "flatpak_system", "flatpak_user"),
    )
    checked = await executor.async_execute(JobAction.CHECK_UPDATES, host)
    assert checked.snapshot.updates == 4
    user = next(p for p in checked.snapshot.packages if p.source == "flatpak_user")
    updated = await executor.async_execute(JobAction.UPDATE, host, user.name)
    assert updated.snapshot.updates == 3
    user_only = host.model_copy(update={"package_sources": ("flatpak_user",)})
    assert (
        await executor.async_execute(JobAction.CHECK_UPDATES, user_only)
    ).snapshot.updates == 0
    # Toggling sources must never resurrect a mock package that was already updated.
    assert (
        await executor.async_execute(JobAction.CHECK_UPDATES, host)
    ).snapshot.updates == 3
    source = "apt" if provider in {"auto", "debian_apt"} else provider
    cleared = await executor.async_execute(JobAction.UPDATE, host, "source::" + source)
    assert cleared.snapshot.updates == 1
    all_done = await executor.async_execute(JobAction.UPDATE, host)
    assert all_done.snapshot.updates == 0
    assert (
        await executor.async_execute(JobAction.CHECK_UPDATES, host)
    ).snapshot.updates == 0
    restarted = await executor.async_execute(JobAction.REBOOT, host)
    assert restarted.snapshot.reboot_required is False


async def test_preview_partial_pacman_and_stale_reference_fail_without_updates():
    executor = PreviewExecutor()
    host = auto_host(package_provider="pacman", package_sources=("system",))
    checked = await executor.async_execute(JobAction.CHECK_UPDATES, host)
    assert checked.snapshot.package_scopes == ("full",)
    with pytest.raises(AutomationExecutionError, match="package_scope_unsupported"):
        await executor.async_execute(
            JobAction.UPDATE, host, checked.snapshot.packages[0].name
        )
    with pytest.raises(AutomationExecutionError, match="package_selection_stale"):
        await executor.async_execute(JobAction.UPDATE, host, "flatpak_user::missing")
    assert (
        await executor.async_execute(JobAction.CHECK_UPDATES, host)
    ).snapshot.updates == 2
