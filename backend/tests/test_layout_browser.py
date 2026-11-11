"""Layout remains stable while notifications, context and timeline previews change."""

import re
from asyncio import Event, wait_for
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from playwright.async_api import Route, async_playwright, expect

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
async def test_toolbar_notifications_orbit_and_quick_reset(
    tmp_path: Path, socket_enabled: None, ingress: bool
) -> None:
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=ingress)
    app = create_app(
        settings,
        executor=FakeExecutor(),
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}) if ingress else None,
    )
    prefix = "/nested/layout" if ingress else ""
    async with (
        _live_server(_PrefixProxy(app, prefix) if ingress else app) as base,
        async_playwright() as api,
    ):
        database = Database(settings.database_path)
        host = await HostRepository(database).async_create(
            HostCreate(
                name="Node 01", address="node-01.example.invalid", username="automation"
            )
        )
        await database.async_execute("UPDATE ui_preferences SET auto_check_enabled=0")
        now = datetime.now(UTC)
        await database.async_execute(
            "UPDATE hosts SET checked_at=?", (now.isoformat(),)
        )
        timestamp = (now - timedelta(hours=1)).isoformat()
        for _ in range(12):
            await database.async_execute(
                "INSERT INTO jobs(id,action,host_id,state,created_at,finished_at) "
                "VALUES(?,?,?,?,?,?)",
                (
                    str(uuid4()),
                    "test_connection",
                    str(host.id),
                    "success",
                    timestamp,
                    timestamp,
                ),
            )
        browser = await api.chromium.launch()
        page = await browser.new_page(
            viewport={"width": 1440, "height": 1000}, has_touch=True
        )
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "console",
            lambda msg: (
                errors.append(msg.text)
                if "Content Security Policy" in msg.text
                else None
            ),
        )
        await page.goto(base + prefix + "/")
        if not ingress:
            await page.locator("#token").fill(TOKEN)
            await page.locator("#connect").click()
        await _wait_for_connection(page)
        brand = await page.locator("h1").bounding_box()
        assert brand is not None
        assert abs(brand["x"] + brand["width"] / 2 - 720) < 2
        tabs = await page.locator("nav").bounding_box()
        status = await page.locator(".toolbar-status").bounding_box()
        auto = await page.locator(".auto-check-control").bounding_box()
        assert tabs is not None
        assert status is not None
        assert auto is not None
        assert tabs["x"] + tabs["width"] < status["x"] < auto["x"]
        assert (
            abs(status["y"] + status["height"] / 2 - tabs["y"] - tabs["height"] / 2) < 2
        )
        marker = page.locator("#history a[data-point]").first
        await marker.focus()
        await expect(page.locator("#history-popover .orbit-job")).to_have_count(6)
        center = await page.locator(
            "#history-popover .orbit-center circle"
        ).bounding_box()
        original = await marker.locator("circle").bounding_box()
        assert center is not None
        assert original is not None
        assert (
            abs(
                center["x"]
                + center["width"] / 2
                - original["x"]
                - original["width"] / 2
            )
            < 1
        )
        assert (
            abs(
                center["y"]
                + center["height"] / 2
                - original["y"]
                - original["height"] / 2
            )
            < 1
        )
        await expect(marker.locator("text")).to_have_text("12")
        await page.screenshot(
            path=f"/tmp/commander-layout-desktop-{ingress}.png", full_page=True
        )
        await page.keyboard.press("Escape")
        await expect(page.locator("#history-popover")).to_be_hidden()
        # A synthetic action links its job without shifting the layout.
        await page.locator('#hosts button[data-action="check_updates"]').click()
        await expect(page.locator("#message-text")).to_have_text("check updates queued")
        await expect(page.locator("#message-link")).to_be_visible()
        job_href = await page.locator("#message-link").get_attribute("href")
        assert job_href is not None
        assert job_href.startswith("#/jobs/")
        after = await page.locator("nav").bounding_box()
        assert after is not None
        assert after["y"] + await page.evaluate("scrollY") == tabs["y"]
        await page.locator("#message-link").click()
        await expect(page.locator("#job-detail")).to_be_visible()
        assert job_href in page.url
        await expect(page.locator("#host-context")).to_contain_text("Job:")
        await page.get_by_role("button", name="Clear selection and filters").click()
        await expect(page).to_have_url(base + prefix + "/#/jobs")
        await expect(page.locator("#job-detail")).to_be_hidden()
        await page.goto(
            base + prefix + f"/#/dashboard?host_id={host.id}&state=success&range=24h"
        )
        await _wait_for_connection(page)
        await expect(page.locator("#host-context")).to_contain_text(
            "Selected host: Node 01"
        )
        await expect(page.locator("#dashboard a").nth(1)).to_have_attribute(
            "href", f"#/jobs?host_id={host.id}&state=running"
        )
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.locator("#host-section").scroll_into_view_if_needed()
        await expect(page.locator("#reset-view")).to_be_in_viewport()
        await page.locator("#reset-view").click()
        await expect(page).to_have_url(base + prefix + "/#/dashboard")
        await expect(page.locator("#filter-count")).to_have_text("0")
        await expect(page.locator("#reset-view")).to_be_disabled()
        await expect(page.locator("#job-state")).to_have_value("")
        await expect(page.locator("#history-range")).to_have_value("7d")
        await page.locator("h1").scroll_into_view_if_needed()
        await marker.focus()
        await marker.scroll_into_view_if_needed()
        await expect(page.locator("#history-popover .orbit-job")).to_have_count(6)
        await page.screenshot(
            path=f"/tmp/commander-layout-mobile-{ingress}.png", full_page=True
        )
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        await page.keyboard.press("Escape")
        await marker.tap()
        await expect(page.locator("#history-popover")).to_be_visible()
        await expect(page).to_have_url(base + prefix + "/#/dashboard")
        # Typing during an outstanding refresh must retain the unsubmitted search.
        requested, release = Event(), Event()

        async def delayed_timeline(route: Route) -> None:
            requested.set()
            await release.wait()
            await route.continue_()

        await page.route("**/ui-api/jobs/timeline?*", delayed_timeline)
        await page.locator("#refresh").click()
        await wait_for(requested.wait(), timeout=5)
        await page.locator("#host-search").fill("Node")
        release.set()
        await expect(page.locator("#message-text")).to_have_text("Data refreshed")
        await expect(page.locator("#host-search")).to_have_value("Node")
        await page.unroute("**/ui-api/jobs/timeline?*", delayed_timeline)
        await page.locator("#host-search").press("Enter")
        await expect(page).to_have_url(re.compile(r"h_search=Node"))
        assert errors == []
        await browser.close()
