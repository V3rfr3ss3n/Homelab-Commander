"""Group workspace works through session and nested Ingress with synthetic data."""

import asyncio
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
            await page.locator('nav a[data-tab="hosts"]').click()
            await page.get_by_role("link", name="Inventory & groups").click()
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
            # A preview of an older draft must not overwrite an edited definition.
            preview_pending, preview_release = asyncio.Event(), asyncio.Event()

            async def hold_preview(route):
                response = await route.fetch()
                preview_pending.set()
                await preview_release.wait()
                await route.fulfill(response=response)

            await page.route("**/ui-api/groups/preview?*", hold_preview)
            await page.locator("#group-preview").click()
            await preview_pending.wait()
            await page.locator("#group-description").fill("Edited while previewing")
            preview_release.set()
            await page.unroute("**/ui-api/groups/preview?*")
            await expect(page.locator("#group-preview")).to_be_enabled()
            await expect(page.locator("#group-preview-result")).to_be_empty()
            assert await page.evaluate("operatorUI.request('groups')") == []
            await page.locator("#group-save").click()
            await expect(page.locator("#group-editor")).to_be_hidden()
            await page.locator(f'[data-resource-detail="{host.id}"]').click()
            await page.locator(f'[data-resource-tags="{host.id}"]').fill(
                "production, linux"
            )
            await page.evaluate("groupWorkspace.load()")
            await expect(
                page.locator(f'[data-resource-tags="{host.id}"]')
            ).to_have_value("production, linux")
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
            await expect(page.locator("#group-editor")).to_be_hidden()
            await page.locator("#group-manage").click()
            await expect(page.locator("#group-list")).to_contain_text("Smart group")
            row = page.locator("#group-list article").filter(
                has_text="Tagged resources"
            )
            await row.locator("[data-edit-group]").click()
            await expect(page.locator("#group-kind")).to_have_value("smart")
            await expect(page.locator("[data-rule-value]")).to_have_value("production")
            await page.locator("#group-name").fill("Renamed smart group")
            await page.locator("#group-save").click()
            await expect(page.locator("#group-editor")).to_be_hidden()
            await page.reload()
            await page.locator("#group-manage").click()
            await expect(page.locator("#group-list")).to_contain_text(
                "Renamed smart group"
            )
            await page.get_by_role("button", name="Close group manager").click()
            await page.locator("#resource-filter-toggle").click()
            await page.locator("#group-resource-kind").select_option("container")
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


@pytest.mark.parametrize("ingress", [False, True])
async def test_resource_list_scope_sort_errors_and_navigation(
    tmp_path: Path, socket_enabled: None, ingress: bool
) -> None:
    """One inventory owns page selection, discovery facets and recoverable errors."""
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=ingress)
    executor = FakeExecutor()
    app = create_app(
        settings,
        executor=executor,
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}) if ingress else None,
    )
    prefix = "/nested/synthetic" if ingress else ""
    async with _live_server(_PrefixProxy(app, prefix) if ingress else app) as base:
        repository = HostRepository(Database(settings.database_path))
        for index in range(28):
            await repository.async_create(
                HostCreate(
                    name=f"Node {index:02}",
                    address=f"node-{index:02}.example.invalid",
                    username="automation",
                )
            )
        async with async_playwright() as api:
            browser = await api.chromium.launch()
            page = await browser.new_page(viewport={"width": 1200, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.route(
                "**/ui-api/preferences/host-checks",
                lambda route: route.fulfill(json={"enabled": False}),
            )
            await page.goto(base + prefix + "/#/resources")
            if not ingress:
                await page.locator("#token").fill(TOKEN)
                await page.locator("#connect").click()
            await _wait_for_connection(page)
            await expect(page.locator("#group-resource-count")).to_have_text(
                "1\u201325 of 28 resources"
            )
            assert await page.locator('nav a[data-tab="groups"]').count() == 0
            bounded = await page.evaluate("""async () => {
                const {ListState} = await import('./list-state.js');
                const state = new ListState();
                const ids = Array.from({length: 500}, (_, index) => String(index));
                const accepted = state.choosePage(ids, true);
                const rejected = !state.choosePage(['extra'], true);
                const rejectedSingle = !state.choose('extra', true);
                state.choosePage(ids.slice(0, 25), false);
                const size = state.selected.size;
                const revision = state.invalidate();
                state.reset();
                return {accepted, rejected, rejectedSingle, size,
                    stale: !state.current(revision),
                    cleared: state.selected.size === 0};
            }""")
            assert bounded == {
                "accepted": True,
                "rejected": True,
                "rejectedSingle": True,
                "size": 475,
                "stale": True,
                "cleared": True,
            }
            await page.locator("#resource-add").click()
            await expect(page.locator("#host-dialog")).to_be_visible()
            await expect(page.locator("#host-dialog-title")).to_have_text("Add host")
            await expect(page.locator("#host-system-step")).to_be_visible()
            await page.get_by_role("button", name="Close host dialog").click()
            await expect(page.locator("#group-editor")).to_be_hidden()
            await expect(page.locator("#resource-filters")).to_be_hidden()
            await page.locator("#resource-select-page").check()
            await page.locator("#group-resources-next").click()
            await expect(page.locator("#resource-selection-summary")).to_have_text(
                "25 selected · 25 outside this page"
            )
            await page.locator("#resource-select-page").check()
            await expect(page.locator("#resource-selection-summary")).to_have_text(
                "28 selected · 25 outside this page"
            )
            await page.locator('[data-resource-sort="name"]').click()
            await expect(page.locator("#group-resources tr").first).to_contain_text(
                "Node 27"
            )
            await expect(
                page.locator('[data-resource-sort="name"]').locator("..")
            ).to_have_attribute("aria-sort", "descending")
            await page.locator("#group-resource-query").fill("Node 00")
            await page.locator("#group-resource-query").press("Enter")
            await expect(page.locator("#group-resource-count")).to_have_text(
                "1\u20131 of 1 resources"
            )
            await expect(page.locator("#resource-selection-summary")).to_have_text(
                "28 selected · 27 outside this page"
            )
            await page.locator("#reset-view").click()
            await expect(page.locator("#resource-selection-summary")).to_have_text(
                "0 selected"
            )
            await expect(page.locator("#group-resource-count")).to_have_text(
                "1\u201325 of 28 resources"
            )
            await expect(page.locator("#group-resources tr").first).to_contain_text(
                "Node 00"
            )
            await page.locator("#group-resources input").first.check()
            await page.locator("#group-new").click()
            await page.locator("#group-name").fill("Single node")
            await page.locator("#group-save").click()
            await expect(page.locator("#group-editor")).to_be_hidden()
            await page.locator("#group-manage").click()
            await page.locator("[data-view-group]").click()
            await expect(page.locator("#group-resource-count")).to_have_text(
                "1\u20131 of 1 resources"
            )
            await page.locator("#resource-filter-toggle").click()
            await expect(page.locator("#resource-group-name")).to_have_text(
                "Single node"
            )
            await page.locator("#group-resource-kind").select_option("container")
            await expect(page.locator("#group-resources")).to_contain_text(
                "No matching resources"
            )
            await page.locator("#resource-clear-filters").click()
            await expect(page.locator("#group-resource-count")).to_have_text(
                "1\u201325 of 28 resources"
            )
            await page.locator("#group-manage").click()
            await page.locator("[data-delete-group]").click()
            await page.locator("#confirm-accept").click()
            await expect(page.locator("#group-list")).to_contain_text("No groups match")
            await page.keyboard.press("Escape")
            await expect(page.locator("#group-manager")).not_to_be_visible()
            await expect(page.locator("#group-manage")).to_be_focused()
            await page.locator("[data-resource-detail]").first.click()
            await expect(page.locator("#resource-detail-title")).to_be_focused()
            await expect(
                page.get_by_role("link", name="Open host details and actions")
            ).to_be_visible()
            await page.screenshot(
                path=str(tmp_path / "resources-wide.png"), full_page=True
            )
            await page.locator("#resource-close").click()
            await expect(page.locator("[data-resource-detail]").first).to_be_focused()
            await page.route(
                "**/ui-api/group-resources?*",
                lambda route: route.fulfill(status=503, json={"detail": "Synthetic"}),
            )
            await page.locator('[data-resource-sort="kind"]').click()
            await expect(page.locator("#resource-load-state")).to_contain_text("stale")
            await expect(page.locator("#resource-select-page")).to_be_disabled()
            await page.unroute("**/ui-api/group-resources?*")
            await page.locator("#resource-retry").click()
            await expect(page.locator("#resource-load-state")).to_be_hidden()
            await expect(page.locator("#message-text")).to_have_text(
                "Resource inventory refreshed."
            )
            await page.route(
                "**/ui-api/group-resources?*",
                lambda route: route.fulfill(json={"items": "invalid", "total": 0}),
            )
            await page.locator('[data-resource-sort="kind"]').click()
            await expect(page.locator("#resource-load-state")).to_contain_text(
                "unavailable"
            )
            await expect(page.locator("#message-text")).to_contain_text(
                "invalid response"
            )
            await page.unroute("**/ui-api/group-resources?*")
            await page.locator("#resource-retry").click()
            await expect(page.locator("#resource-load-state")).to_be_hidden()
            await expect(page.locator("#message-text")).to_have_text(
                "Resource inventory refreshed."
            )
            # A pending read after navigation must not repopulate cleared inventory.
            pending, release = asyncio.Event(), asyncio.Event()

            async def hold(route):
                response = await route.fetch()
                pending.set()
                await release.wait()
                await route.fulfill(response=response)

            await page.route("**/ui-api/group-resources?*", hold)
            await page.locator('[data-resource-sort="name"]').click()
            await pending.wait()
            await page.locator('nav a[data-tab="tasks"]').click()
            await expect(page.locator("#group-resources")).to_be_empty()
            release.set()
            await page.unroute_all(behavior="wait")
            await expect(page.locator("#group-resources")).to_be_empty()
            await page.goto(base + prefix + "/#/resources")
            await expect(page.locator("#group-resource-count")).to_have_text(
                "1\u201325 of 28 resources"
            )
            await page.set_viewport_size({"width": 390, "height": 844})
            await page.locator("#group-new").click()
            await expect(page.locator("#group-name")).to_be_focused()
            assert await page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            )
            await page.screenshot(
                path=str(tmp_path / "resources-mobile.png"), full_page=True
            )
            await page.locator("#group-name").fill("Unsaved draft")
            await page.evaluate("setDisconnected()")
            await expect(page.locator("#group-resources")).to_be_empty()
            await expect(page.locator("#group-name")).to_have_value("")
            assert executor.calls == []
            assert errors == []
            await browser.close()
