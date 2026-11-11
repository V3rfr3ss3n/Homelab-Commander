"""Timestamp graph, orbit drill-down and table filters under both UI modes."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from playwright.async_api import async_playwright, expect

from backend.homelab_backend.app import create_app
from backend.homelab_backend.config import Settings
from backend.homelab_backend.custom_tasks import CustomTaskRepository
from backend.homelab_backend.database import Database
from backend.homelab_backend.hosts import HostRepository
from backend.homelab_backend.models import CustomTaskCreate, HostCreate
from backend.tests.test_backend_api import TOKEN, FakeExecutor
from backend.tests.test_ui_browser import (
    _live_server,
    _PrefixProxy,
    _wait_for_connection,
)


@pytest.mark.parametrize("ingress", [False, True])
async def test_timeline_group_opens_exact_table_window(
    tmp_path: Path,
    socket_enabled: None,
    ingress: bool,
) -> None:
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=ingress)
    app = create_app(
        settings,
        executor=FakeExecutor(),
        ingress_proxy_addresses=(frozenset({"supervisor-proxy"}) if ingress else None),
    )
    prefix = "/nested/synthetic" if ingress else ""
    async with _live_server(_PrefixProxy(app, prefix) if ingress else app) as base:
        db = Database(settings.database_path)
        first = await HostRepository(db).async_create(
            HostCreate(
                name="Node B",
                address="node-b.example.invalid",
                username="automation",
            )
        )
        await HostRepository(db).async_create(
            HostCreate(
                name="Node A",
                address="node-a.example.invalid",
                username="automation",
            )
        )
        await CustomTaskRepository(db, allow_shell=False).async_create(
            CustomTaskCreate(
                name="Enabled task",
                argv=("uptime",),
            )
        )
        await CustomTaskRepository(db, allow_shell=False).async_create(
            CustomTaskCreate(
                name="Disabled task",
                argv=("uptime",),
                enabled=False,
            )
        )
        now = datetime.now(UTC)
        await db.async_execute(
            "UPDATE hosts SET checked_at=?, updates=2, "
            "distribution='Debian', distribution_version='12' WHERE id=?",
            (now.isoformat(), str(first.id)),
        )
        grouped_time = now - timedelta(hours=5)
        single_time = now - timedelta(hours=2)
        for index in range(4):
            when = grouped_time if index < 3 else single_time
            await db.async_execute(
                "INSERT INTO jobs(id,action,host_id,state,created_at,finished_at) "
                "VALUES(?,?,?,?,?,?)",
                (
                    str(uuid4()),
                    "check_updates" if index == 3 else "test_connection",
                    str(first.id),
                    "failed" if index == 1 else "success",
                    when.isoformat(),
                    when.isoformat(),
                ),
            )
        async with async_playwright() as api:
            browser = await api.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 390, "height": 844})
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
            await page.route(
                "**/ui-api/preferences/host-checks",
                lambda route: route.fulfill(json={"enabled": False}),
            )
            await page.goto(base + prefix + "/")
            if not ingress:
                await page.locator("#token").fill(TOKEN)
                await page.locator("#connect").click()
            await _wait_for_connection(page)
            await page.locator("#history-range").select_option("24h")
            await expect(page.locator("#history-total")).to_have_text("4 jobs")
            assert await page.locator("#history .timeline-point").count() == 2
            group = page.locator("#history a[data-point]").first
            assert await group.get_attribute("data-anchor-state") == "success"
            assert await group.get_attribute("data-anchor-count") == "2"
            await expect(group.locator("circle")).to_have_css(
                "fill", "rgb(237, 140, 152)"
            )
            await group.hover(force=True)
            await expect(page.locator("#history-popover .orbit-job")).to_have_count(3)
            center = page.locator("#history-popover .orbit-center")
            await center.focus()
            await group.locator("text").dispatch_event(
                "pointerover", {"pointerType": "mouse"}
            )
            await expect(center).to_be_focused()
            await center.click()
            await expect(page.locator("#jobs-section")).to_be_visible()
            await expect(page.locator("#history-total")).to_have_text("3 jobs")
            assert "display=table" in page.url
            assert "start=" in page.url
            assert await page.locator("#jobs .row").count() == 3
            await page.locator("#job-state").select_option("failed")
            await expect(page.locator("#history-total")).to_have_text("1 job")
            await page.locator("#history-reset").click()
            await expect(page.locator("#history-total")).to_have_text("4 jobs")
            await page.locator("#history-toggle").click()
            await expect(page.locator("#history-chart")).to_be_visible()
            await page.locator('nav a[data-tab="dashboard"]').click()
            await page.screenshot(
                path=f"/tmp/timeline-dashboard-{ingress}.png", full_page=True
            )
            await page.locator("#host-search").fill("Node B")
            await page.evaluate("location.hash='/hosts'")
            await expect(page.locator("#host-list-slot #host-controls")).to_be_visible()
            await expect(page.locator("#host-search")).to_be_focused()
            await expect(page.locator("#host-search")).to_have_value("Node B")
            await page.locator("#host-search").press("Enter")
            await expect(page.locator("#host-count")).to_have_text("1 of 2 hosts")
            assert await page.locator("#hosts .row").count() == 1
            await expect(page.locator("#update-shown")).to_be_enabled()

            await page.locator("#update-shown").click()
            await expect(page.locator("#confirm-dialog")).to_be_visible()
            await expect(page.locator("#confirm-targets")).to_contain_text("Node B")
            await page.locator("#confirm-cancel").click()
            assert (
                await db.async_fetch_one(
                    "SELECT COUNT(*) AS count FROM jobs WHERE action='update'"
                )
            )["count"] == 0
            await page.locator("#update-shown").click()
            await page.locator("#confirm-ack").check()
            await page.locator("#confirm-accept").click()
            await expect(page.locator("#message-text")).to_have_text("Updates queued")
            assert (
                await db.async_fetch_one(
                    "SELECT COUNT(*) AS count FROM jobs WHERE action='update'"
                )
            )["count"] == 1
            await page.locator('nav a[data-tab="tasks"]').click()
            await page.locator("#task-filter").select_option("disabled")
            await expect(page.locator("#task-count")).to_have_text("1 of 2 tasks")
            await expect(page.locator("#tasks")).to_contain_text("Disabled task")
            await expect(page.locator("#tasks")).not_to_contain_text("Enabled task")
            await page.screenshot(
                path=f"/tmp/timeline-mobile-{ingress}.png", full_page=True
            )
            assert errors == []
            await browser.close()
