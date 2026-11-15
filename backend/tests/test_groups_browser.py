"""Group workspace works through session and nested Ingress with synthetic data."""

from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect

from backend.homelab_backend.app import create_app
from backend.homelab_backend.config import Settings
from backend.homelab_backend.database import Database
from backend.homelab_backend.hosts import HostRepository
from backend.homelab_backend.models import HostCreate
from backend.tests.test_backend_api import TOKEN, FakeExecutor
from backend.tests.test_ui_browser import (
    _live_server,
    _PrefixProxy,
    _wait_for_connection,
)


@pytest.mark.parametrize("ingress", [False, True])
async def test_groups_workspace_preview_membership_tags_and_edit(
    tmp_path: Path, socket_enabled: None, ingress: bool
) -> None:
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=ingress)
    executor = FakeExecutor()
    app = create_app(
        settings,
        executor=executor,
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}) if ingress else None,
    )
    prefix = "/nested/synthetic" if ingress else ""
    async with _live_server(_PrefixProxy(app, prefix) if ingress else app) as base:
        host = await HostRepository(Database(settings.database_path)).async_create(
            HostCreate(
                name="Node 01", address="node-01.example.invalid", username="automation"
            )
        )
        async with async_playwright() as api:
            browser = await api.chromium.launch()
            page = await browser.new_page(viewport={"width": 1100, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.route(
                "**/ui-api/preferences/host-checks",
                lambda route: route.fulfill(json={"enabled": False}),
            )
            await page.goto(base + prefix + "/")
            if not ingress:
                await page.locator("#token").fill(TOKEN)
                await page.locator("#connect").click()
            await _wait_for_connection(page)
            await page.locator('nav a[data-tab="groups"]').click()
            await expect(page.locator("#groups-workspace")).to_be_visible()
            await expect(page.locator("#group-resources")).to_contain_text("Node 01")
            await page.locator("#group-new").click()
            await page.locator("#group-name").fill("Production")
            await page.locator(f'[data-group-member="{host.id}"]').check()
            await page.locator("#group-clear-selection").click()
            await expect(
                page.locator(f'[data-group-member="{host.id}"]')
            ).not_to_be_checked()
            await page.locator(f'[data-group-member="{host.id}"]').check()
            await page.route(
                "**/ui-api/groups/preview?*",
                lambda route: route.fulfill(
                    status=503,
                    json={"detail": "Synthetic unavailable", "error_code": "http_503"},
                ),
            )
            await page.locator("#group-preview").click()
            await expect(page.locator("#group-preview-result")).to_contain_text(
                "Preview unavailable"
            )
            await page.unroute("**/ui-api/groups/preview?*")
            await page.locator("#group-preview").click()
            await expect(page.locator("#group-preview-result")).to_contain_text(
                "1 matching resources"
            )
            await expect(page.locator("#group-list")).to_contain_text("No groups match")
            await page.locator("#group-save").click()
            await expect(page.locator("#group-list")).to_contain_text("Production")
            await page.locator(f'[data-resource-tags="{host.id}"]').fill(
                "production, linux"
            )
            await page.locator(f'[data-save-tags="{host.id}"]').click()
            await expect(page.locator("#message-text")).to_have_text("Tags saved")
            await page.locator("#group-new").click()
            await page.locator("#group-name").fill("Tagged resources")
            await page.locator("#group-kind").select_option("smart")
            await page.locator("[data-rule-field]").select_option("tag")
            await page.locator("[data-rule-value]").fill("production")
            await page.locator("#group-preview").click()
            await expect(page.locator("#group-preview-result")).to_contain_text(
                "Node 01"
            )
            await page.locator("#group-save").click()
            await expect(page.locator("#group-list")).to_contain_text("Smart group")
            row = page.locator("#group-list article").filter(
                has_text="Tagged resources"
            )
            await row.locator("[data-edit-group]").click()
            await expect(page.locator("#group-kind")).to_have_value("smart")
            await expect(page.locator("[data-rule-value]")).to_have_value("production")
            await page.locator("#group-name").fill("Renamed smart group")
            await page.locator("#group-save").click()
            await expect(page.locator("#group-list")).to_contain_text(
                "Renamed smart group"
            )
            await page.reload()
            await expect(page.locator("#group-list")).to_contain_text(
                "Renamed smart group"
            )
            await page.locator("#group-resource-kind").select_option("container")
            await page.locator("#group-resource-search button").click()
            await expect(page.locator("#group-resources")).to_contain_text(
                "No matching resources"
            )
            await page.locator("#group-new").click()
            await page.locator("#group-name").fill("Synthetic private draft")
            await page.evaluate("setDisconnected()")
            await expect(page.locator("#group-name")).to_have_value("")
            await expect(page.locator("#group-resources")).to_be_empty()
            assert errors == []
            assert executor.calls == []
            await browser.close()
