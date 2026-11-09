"""Readable dashboard, website shortcuts and opt-out visible checks in a browser."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect

from backend.homelab_backend.app import create_app
from backend.homelab_backend.config import Settings
from backend.homelab_backend.database import Database
from backend.homelab_backend.hosts import HostRepository
from backend.homelab_backend.jobs import JobRepository
from backend.homelab_backend.models import HostCreate, HostWebsite, JobAction, JobState
from backend.tests.test_backend_api import TOKEN, FakeExecutor
from backend.tests.test_ui_browser import (
    _live_server,
    _PrefixProxy,
    _wait_for_connection,
    _wait_for_message,
)


@pytest.mark.parametrize("ingress", [False, True])
async def test_readable_dashboard_shortcuts_graph_and_visible_checks(
    tmp_path: Path, socket_enabled: None, ingress: bool
) -> None:
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=ingress)
    executor = FakeExecutor()
    app = create_app(
        settings,
        executor=executor,
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}) if ingress else None,
    )
    prefix = "/nested/demo" if ingress else ""
    async with (
        _live_server(_PrefixProxy(app, prefix) if ingress else app) as base,
        async_playwright() as api,
    ):
        database = Database(settings.database_path)
        hosts = HostRepository(database)
        host = await hosts.async_create(
            HostCreate(
                name="Node 01",
                address="node-01.example.invalid",
                username="automation",
                websites=(
                    HostWebsite(name="Portal", url="https://portal.example.invalid/ui"),
                ),
            )
        )
        second = await hosts.async_create(
            HostCreate(
                name="Node 02", address="node-02.example.invalid", username="automation"
            )
        )
        await database.async_execute(
            "UPDATE hosts SET checked_at=? WHERE id=?",
            (datetime.now(UTC).isoformat(), str(second.id)),
        )
        jobs = JobRepository(database)
        failure = await jobs.async_create(JobAction.TEST_CONNECTION, host.id)
        await jobs.async_finish(
            failure.id,
            state=JobState.FAILED,
            output="Synthetic <safe> log preview",
            truncated=False,
            error_code="sudo_unavailable",
        )
        browser = await api.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 1000})
        # Website icons and navigation use synthetic network responses.
        await context.route(
            "https://portal.example.invalid/**",
            lambda route: route.fulfill(
                content_type="text/html"
                if route.request.is_navigation_request()
                else "image/svg+xml",
                body="<h1>Demo portal</h1>"
                if route.request.is_navigation_request()
                else (
                    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
                    '<circle cx="8" cy="8" r="7" fill="green"/></svg>'
                ),
            ),
        )
        page = await context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        auto_requests = []
        page.on(
            "request",
            lambda req: (
                auto_requests.append(req.url)
                if req.url.endswith("/actions/check-visible")
                else None
            ),
        )
        await page.clock.install()
        async with page.expect_response("**/ui-api/actions/check-visible"):
            await page.goto(base + prefix + "/")
            if not ingress:
                await page.locator("#token").fill(TOKEN)
                await page.locator("#connect").click()
        await _wait_for_connection(page)
        await expect(page.locator("#backend-status")).to_have_class(
            "backend-status online"
        )
        assert await page.get_by_text("HC", exact=True).count() == 0
        assert await page.locator("#dashboard .metric small").all_text_contents() == [
            "Hosts",
            "Running jobs",
            "Queued jobs",
        ]
        assert await page.locator("#history polyline").count() == 5
        assert await page.locator("#history rect").count() == 0
        assert await page.locator("#history circle").count() == 35
        await expect(page.locator("#notices-panel")).to_be_visible()
        assert await page.locator(
            "#hosts .row > span:first-child > a"
        ).all_text_contents() == [
            "Node 01",
            "Node 02",
        ]
        assert await page.get_by_role("link", name="Details", exact=True).count() == 2
        assert (
            await page.locator(
                "#hosts [data-action=check_updates]"
            ).first.get_attribute("title")
            == "Check for updates"
        )
        last_failure = page.locator(".job-highlight").filter(
            has=page.get_by_text("Last failed job", exact=True)
        )
        assert "Connection test" in await last_failure.inner_text()
        assert "sudo_unavailable" not in await last_failure.inner_text()
        await last_failure.locator("[data-preview-log]").click()
        await expect(page.locator("#log-preview-output")).to_have_text(
            "Synthetic <safe> log preview"
        )
        await page.get_by_role("button", name="Close log preview").click()
        async with page.expect_popup() as popup_event:
            await page.get_by_role("link", name="Open Portal").click()
        popup = await popup_event.value
        await expect(popup.get_by_role("heading", name="Demo portal")).to_be_visible()
        await popup.close()
        # A real line graph and sidebar are visible in the desktop artifact.
        await page.screenshot(
            path=f"/tmp/commander-refined-desktop-{ingress}.png", full_page=True
        )
        await page.clock.pause_at(datetime.now(UTC) + timedelta(seconds=1))
        async with page.expect_response("**/ui-api/actions/check-visible"):
            await page.clock.run_for(300001)
        assert len(auto_requests) == 2
        await page.wait_for_function("() => !visibleCheckInFlight")
        # Visibility is a controlled browser boundary; no wall-clock sleeps are needed.
        await page.evaluate(
            "Object.defineProperty(document,'visibilityState',{configurable:true,"
            "get:()=>window.demoVisibility||'visible'});window.demoVisibility='hidden';"
            "document.dispatchEvent(new Event('visibilitychange'))"
        )
        await page.clock.run_for(300001)
        assert len(auto_requests) == 2
        async with page.expect_response("**/ui-api/actions/check-visible"):
            await page.evaluate(
                "window.demoVisibility='visible';"
                "document.dispatchEvent(new Event('visibilitychange'))"
            )
            await page.clock.run_for(1)
        assert len(auto_requests) == 3
        await page.locator('nav a[href="#/tasks"]').click()
        await page.locator("#tasks").wait_for(state="visible")
        await page.clock.run_for(300001)
        assert len(auto_requests) == 3
        await page.locator("#auto-host-checks").uncheck()
        await _wait_for_message(page, "Host check preference saved")
        await page.locator('nav a[href="#/dashboard"]').click()
        await page.locator("#dashboard").wait_for(state="visible")
        await page.clock.run_for(300001)
        assert len(auto_requests) == 3
        # Resolving attention removes the sidebar without deleting historical failure.
        resolution = await jobs.async_create(JobAction.TEST_CONNECTION, host.id)
        await jobs.async_finish(
            resolution.id,
            state=JobState.SUCCESS,
            output="Synthetic recovery",
            truncated=False,
        )
        await database.async_execute(
            "UPDATE hosts SET updates=0,security_updates=0,"
            "reboot_required=0,checked_at=?",
            (datetime.now(UTC).isoformat(),),
        )
        await page.locator("#connect").click()
        await _wait_for_connection(page)
        await expect(page.locator("#notices-panel")).to_be_hidden()
        await expect(page.locator("#auto-host-checks")).not_to_be_checked()
        assert await last_failure.locator("[data-preview-log]").count() == 1
        await page.get_by_role("link", name="Details", exact=True).first.click()
        await page.locator("#host-detail").wait_for(state="visible")
        assert await page.locator("#host-info time").get_attribute("title")
        assert "T" not in await page.locator("#host-info time").inner_text()
        await page.locator("[data-edit-host]").click()
        assert (
            "Portal | https://portal.example.invalid/ui"
            in await page.locator("#host-websites").input_value()
        )
        await page.locator("#host-websites").fill("Unsafe | javascript:alert(1)")
        await page.locator("#host-form button[type=submit]").click()
        await expect(page.locator("#host-form-error")).to_contain_text("HTTP(S)")
        await page.locator("#host-websites").fill(
            "Portal | https://portal.example.invalid/ui"
        )
        await page.locator("#host-websites").fill(
            'Portal " onclick="alert(1) | https://portal.example.invalid/ui'
        )
        await page.locator("#host-form button[type=submit]").click()
        await _wait_for_message(page, "Host updated")
        shortcut = page.locator("#host-info .website-icon")
        assert await shortcut.get_attribute("onclick") is None
        assert await shortcut.get_attribute("title") == 'Portal " onclick="alert(1)'
        await page.locator('nav a[href="#/dashboard"]').click()
        await page.locator("#dashboard").wait_for(state="visible")
        await page.set_viewport_size({"width": 390, "height": 844})
        assert await page.evaluate(
            "document.documentElement.scrollWidth<=window.innerWidth"
        )
        assert await page.locator("#history").evaluate(
            "chart => chart.scrollWidth > chart.clientWidth"
        )
        await page.screenshot(
            path=f"/tmp/commander-refined-mobile-{ingress}.png", full_page=True
        )
        assert errors == []
        await browser.close()
