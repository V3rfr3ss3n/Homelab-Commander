"""Source-aware selection and native update scope in standalone and Ingress."""

import pytest
from playwright.async_api import async_playwright, expect

from backend.homelab_backend.app import create_app
from backend.homelab_backend.config import Settings
from backend.homelab_backend.database import Database
from backend.homelab_backend.hosts import HostRepository
from backend.homelab_backend.models import HostCreate
from backend.tests.test_backend_api import TOKEN
from backend.tests.test_package_sources import SourcesRunner
from backend.tests.test_rpm_providers import executor
from backend.tests.test_ui_browser import (
    _live_server,
    _PrefixProxy,
    _wait_for_connection,
)


@pytest.mark.parametrize("ingress", [False, True])
@pytest.mark.parametrize("system_manager", ["dnf", "pacman", "apt"])
async def test_sources_list_selection_source_update_and_config(
    tmp_path, socket_enabled, ingress, system_manager
):
    pacman = system_manager == "pacman"
    runner = SourcesRunner(pacman=pacman, apt=system_manager == "apt")
    native = executor(tmp_path, runner)
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=ingress)
    app = create_app(
        settings,
        executor=native,
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}) if ingress else None,
    )
    db = Database(settings.database_path)
    await db.async_migrate()
    host = await HostRepository(db).async_create(
        HostCreate(
            name="Synthetic multiple sources",
            address="sources.example.invalid",
            username="automation",
            package_provider="auto",
        )
    )
    await db.async_execute("UPDATE ui_preferences SET auto_check_enabled=0")
    prefix = "/nested/sources" if ingress else ""
    async with (
        _live_server(_PrefixProxy(app, prefix) if ingress else app) as base,
        async_playwright() as api,
    ):
        browser = await api.chromium.launch()
        page = await browser.new_page()
        if ingress:
            await page.set_viewport_size({"width": 390, "height": 844})
        try:
            await page.goto(base + prefix + "/")
            if not ingress:
                await page.locator("#token").fill(TOKEN)
                await page.locator("#connect").click()
            await _wait_for_connection(page)
            await page.goto(base + prefix + f"/#/hosts/{host.id}")
            await expect(page.locator("#host-info")).to_contain_text(
                "Synthetic multiple sources"
            )
            await page.locator(".package-details-toggle").click()
            await page.locator("#package-check").click()
            await expect(
                page.locator("#host-info .host-metric-link").first
            ).to_contain_text("6")
            rows = page.locator("#package-dialog .package-row")
            await expect(rows).to_have_count(6)
            await expect(page.locator(".package-source-summary")).to_have_count(3)
            await expect(page.locator("#package-dialog")).to_contain_text(
                "Flatpak · system"
            )
            await expect(page.locator("#package-dialog")).to_contain_text(
                "Flatpak · SSH user"
            )
            if pacman:
                await page.get_by_text("Pacman upgrade preview (3)").click()
                await expect(
                    page.get_by_role("list", name="Pacman upgrade candidates")
                ).to_contain_text("demo-runtime")
                await page.get_by_text("Foreign packages (1)").click()
                await expect(
                    page.get_by_role("list", name="Foreign packages")
                ).to_contain_text("demo-local")
                system_row = rows.filter(has_text="curl.x86_64")
                await expect(system_row.locator(".package-update-btn")).to_be_disabled()
                await expect(system_row).to_contain_text("Full source upgrade only")
                await page.locator("#package-dialog [data-close-dialog]").click()
                await page.locator('#host-info [data-action="update"]').click()
                await expect(page.locator("#confirm-title")).to_have_text(
                    "Run full Pacman upgrade?"
                )
                await expect(page.locator("#confirm-targets")).to_contain_text(
                    "Pacman full system upgrade, Flatpak · system, Flatpak · SSH user"
                )
                await expect(page.locator("#confirm-targets")).to_contain_text(
                    "Restart status unknown"
                )
                await expect(page.locator("#confirm-accept")).to_be_disabled()
                await page.locator("#confirm-cancel").click()
                assert runner.writes == 0
                await page.locator(".package-details-toggle").click()
            await page.locator("#package-skip-all").click()
            user_row = rows.filter(has_text="org.example.Editor").filter(
                has_text="Flatpak · SSH user"
            )
            await user_row.locator("[data-skip-name]").uncheck()
            await expect(page.locator("#package-update-selected")).to_have_text(
                "Update selected (1)"
            )
            await page.locator("#package-update-selected").click()
            await expect(page.locator("#confirm-description")).to_contain_text(
                "Sources run sequentially"
            )
            await page.locator("#confirm-ack").check()
            await page.locator("#confirm-accept").click()
            await expect(rows).to_have_count(5)
            await expect(
                rows.filter(has_text="org.example.Editor").filter(
                    has_text="Flatpak · system"
                )
            ).to_have_count(1)
            if system_manager == "apt":
                await expect(page.locator("#notices")).to_contain_text(
                    "1 host has security updates"
                )
                await expect(page.locator("#host-info")).to_contain_text(
                    "known security updates"
                )
            system_key = system_manager
            await page.locator(f'[data-package="source::{system_key}"]').click()
            await expect(page.locator("#confirm-description")).to_contain_text(
                "every eligible package"
            )
            if pacman:
                await expect(page.locator("#confirm-description")).to_contain_text(
                    "Pacman runs a full system upgrade"
                )
                await expect(page.locator("#confirm-description")).to_contain_text(
                    "may replace packages"
                )
                await expect(page.locator("#confirm-accept")).to_be_disabled()
            await page.locator("#confirm-ack").check()
            await page.locator("#confirm-accept").click()
            await expect(rows).to_have_count(3)
            assert runner.writes == 1
            await page.locator("#package-dialog [data-close-dialog]").click()
            await page.locator("[data-edit-host]").click()
            await page.locator("#host-source-mode").select_option("manual")
            await expect(page.locator("#host-source-choices")).to_be_visible()
            await page.locator('#host-source-choices input[value="system"]').uncheck()
            await page.locator(
                '#host-source-choices input[value="flatpak_system"]'
            ).uncheck()
            await page.locator('#host-form button[type="submit"]').click()
            await expect(page.locator("#host-dialog")).not_to_be_visible()
            await expect(page.locator("#host-info")).to_contain_text(
                "Synthetic multiple sources"
            )
            await page.locator(".package-details-toggle").click()
            await page.locator("#package-check").click()
            await expect(
                page.locator("#host-info .host-metric-link").first
            ).to_contain_text("1")
            await expect(page.locator(".package-source-summary")).to_have_count(1)
            await expect(page.locator(".package-source-summary")).to_contain_text(
                "Flatpak · SSH user"
            )
        finally:
            await browser.close()
