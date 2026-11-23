"""Standalone/Ingress RPM UI regression using the injected native fixture runner."""

from datetime import UTC, datetime

import pytest
from playwright.async_api import async_playwright, expect

from backend.homelab_backend.app import create_app
from backend.homelab_backend.config import Settings
from backend.homelab_backend.database import Database
from backend.homelab_backend.hosts import HostRepository
from backend.homelab_backend.models import HostCreate, PackageInfo
from backend.tests.test_backend_api import TOKEN
from backend.tests.test_rpm_providers import RpmRunner, executor
from backend.tests.test_ui_browser import (
    _live_server,
    _PrefixProxy,
    _wait_for_connection,
)


@pytest.mark.parametrize("ingress", [False, True])
@pytest.mark.parametrize("native_provider", ["dnf", "auto"])
async def test_rpm_unknown_signals_scopes_and_single_update(
    tmp_path, socket_enabled, ingress, native_provider
):
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=ingress)
    runner = RpmRunner()
    app = create_app(
        settings,
        executor=executor(tmp_path, runner),
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}) if ingress else None,
    )
    database = Database(settings.database_path)
    await database.async_migrate()
    hosts = HostRepository(database)
    native = await hosts.async_create(
        HostCreate(
            name="Synthetic RPM node",
            address="rpm-node.example.invalid",
            username="automation",
            package_provider=native_provider,
        )
    )
    readonly = await hosts.async_create(
        HostCreate(
            name="Read-only rolling node",
            address="rolling-node.example.invalid",
            username="automation",
            package_provider="zypper",
        )
    )
    for host, distro, version, scopes in (
        (native, "Fedora", "45", ("full", "single", "selected")),
        (readonly, "openSUSE Tumbleweed", "20261118", ()),
    ):
        await hosts.async_update_status(
            host.id,
            distribution=distro,
            distribution_version=version,
            kernel="synthetic",
            updates=2,
            security_updates=None,
            reboot_required=None,
            status="ok",
            checked_at=datetime.now(UTC),
            package_scopes=scopes,
            packages=tuple(
                PackageInfo(
                    name=(
                        "dnf::"
                        if native_provider == "auto" and host.id == native.id
                        else ""
                    )
                    + n
                    + ".x86_64",
                    display_name=n + ".x86_64",
                    old_version="0:1-1",
                    new_version="0:2-1",
                    is_security=None,
                )
                for n in ("curl", "git")
            ),
        )
    await database.async_execute("UPDATE ui_preferences SET auto_check_enabled=0")
    prefix = "/nested/rpm" if ingress else ""
    async with (
        _live_server(_PrefixProxy(app, prefix) if ingress else app) as base,
        async_playwright() as api,
    ):
        browser = await api.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(base + prefix + "/")
            if not ingress:
                await page.locator("#token").fill(TOKEN)
                await page.locator("#connect").click()
            await _wait_for_connection(page)
            await expect(page.locator("#notices")).to_contain_text(
                "unknown security or restart status"
            )
            await page.goto(base + prefix + f"/#/hosts/{native.id}")
            await expect(page.locator("#host-info")).to_contain_text(
                "Security status unknown"
            )
            await expect(page.locator("#host-info")).to_contain_text(
                "Restart status unknown"
            )
            await page.locator("[data-edit-host]").click()
            await expect(page.locator("#host-provider")).to_have_value(native_provider)
            await expect(
                page.locator("#host-provider option[value=zypper]")
            ).to_have_count(1)
            await page.locator("#host-dialog [data-close-dialog]").click()
            await page.locator(".package-details-toggle").click()
            rows = page.locator("#package-dialog .package-row")
            await page.locator("#package-check").click()
            await expect(rows).to_have_count(2)
            await expect(rows.first).to_contain_text("Security unknown")
            await (
                rows
                .filter(has_text="curl.x86_64")
                .locator(".package-update-btn")
                .click()
            )
            await expect(page.locator("#confirm-title")).to_contain_text("curl.x86_64")
            await page.locator("#confirm-ack").check()
            await page.locator("#confirm-accept").click()
            await expect(rows).to_have_count(1)
            await expect(rows.first).to_contain_text("git.x86_64")
            assert runner.writes == 1
            await page.locator("#package-dialog [data-close-dialog]").click()
            runner.facts.update(
                ansible_distribution="openSUSE Tumbleweed",
                ansible_distribution_version="20261118",
                ansible_pkg_mgr="zypper",
            )
            await page.goto(base + prefix + f"/#/hosts/{readonly.id}")
            await expect(
                page.locator('#host-info button[data-action="update"]')
            ).to_be_disabled()
            await page.locator(".package-details-toggle").click()
            await page.locator("#package-check").click()
            await expect(rows).to_have_count(1)
            await expect(page.locator("#package-update-all")).to_be_disabled()
            await expect(page.locator("#package-update-selected")).to_be_disabled()
            for button in await page.locator(".package-update-btn").all():
                await expect(button).to_be_disabled()
            await page.locator("#package-dialog [data-close-dialog]").click()
            await page.goto(base + prefix + "/#/hosts")
            await page.locator("[data-add-host]").first.click()
            await page.locator("#host-skip-setup").click()
            await expect(page.locator("#host-provider")).to_have_value("auto")
        finally:
            await browser.close()
