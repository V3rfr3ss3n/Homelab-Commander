"""Maintenance attention, compact filters and useful host details without host I/O."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect

from backend.homelab_backend.app import create_app
from backend.homelab_backend.config import Settings
from backend.homelab_backend.database import Database
from backend.homelab_backend.hosts import HostRepository
from backend.homelab_backend.jobs import JobRepository
from backend.homelab_backend.models import HostCreate, JobAction, JobState
from backend.tests.test_backend_api import TOKEN, FakeExecutor
from backend.tests.test_ui_browser import (
    _live_server,
    _PrefixProxy,
    _wait_for_connection,
)


@pytest.mark.parametrize("ingress", [False, True])
async def test_host_workspace_icons_filters_and_guarded_bulk_updates(
    tmp_path: Path, socket_enabled: None, ingress: bool
) -> None:
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=ingress)
    app = create_app(
        settings,
        executor=FakeExecutor(),
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}) if ingress else None,
    )
    prefix = "/nested/host-workspace" if ingress else ""
    async with (
        _live_server(_PrefixProxy(app, prefix) if ingress else app) as base,
        async_playwright() as api,
    ):
        database = Database(settings.database_path)
        repository = HostRepository(database)
        first = None
        for name, os, version, updates, reboot, kernel in [
            ("Alpha node", "Debian", "12", 12, True, "6.8-synthetic"),
            ("Beta node", "Ubuntu", "24.04", 3, False, "6.8-synthetic"),
            ("Gamma node", "Debian", "12", 0, False, "6.8-pve"),
        ]:
            host = await repository.async_create(
                HostCreate(
                    name=name,
                    address=f"node-{name.split()[0].lower()}.example.invalid",
                    username="automation",
                )
            )
            first = first or host
            await database.async_execute(
                "UPDATE hosts SET distribution=?,distribution_version=?,updates=?,"
                "security_updates=?,reboot_required=?,kernel=?,checked_at=? WHERE id=?",
                (
                    os,
                    version,
                    updates,
                    int(updates > 0),
                    int(reboot),
                    kernel,
                    datetime.now(UTC).isoformat(),
                    str(host.id),
                ),
            )
        assert first is not None
        await database.async_execute("UPDATE ui_preferences SET auto_check_enabled=0")
        jobs = JobRepository(database)
        job = await jobs.async_create(JobAction.CHECK_UPDATES, first.id)
        await jobs.async_finish(
            job.id,
            state=JobState.SUCCESS,
            output="Synthetic check",
            truncated=False,
            exit_code=0,
            reboot_required=True,
        )
        browser = await api.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1050})
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
        await expect(page.locator("#dashboard-sidebar #host-section")).to_be_visible()
        graph = await page.locator("#history-section").bounding_box()
        hosts = await page.locator("#host-section").bounding_box()
        notices = await page.locator("#notices-panel").bounding_box()
        assert graph is not None
        assert hosts is not None
        assert notices is not None
        assert hosts["x"] > graph["x"] + graph["width"]
        assert hosts["y"] > notices["y"] + notices["height"]
        await expect(page.locator("#hosts .has-updates")).to_have_count(2)
        await expect(page.locator("#hosts .restart-required")).to_have_count(1)
        assert (
            "reboot not required"
            not in (await page.locator("#hosts").inner_text()).lower()
        )
        for os in ["debian", "ubuntu", "proxmox"]:
            await expect(page.locator(f'#hosts [data-os="{os}"]')).to_have_count(1)
        await expect(page.locator('#job-filters button[type="submit"]')).to_have_count(
            0
        )
        await expect(page.locator("#job-sort-label")).to_be_hidden()
        await page.screenshot(
            path=f"/tmp/commander-host-sidebar-{ingress}.png", full_page=True
        )
        await page.locator("#history-range").select_option("custom")
        await page.locator("#history-start").fill("2026-11-01T00:00")
        await page.locator("#history-end").fill("2026-11-12T00:00")
        await page.locator("#history-title").click()
        await expect(page.locator("#filter-count")).to_have_text("1")
        await expect(page.locator("#history-range")).to_have_value("custom")
        await expect(page.locator("#history-end")).to_have_value("2026-11-12T00:00")
        await page.locator("#reset-view").click()
        await page.locator('nav a[data-tab="hosts"]').click()
        await expect(page.locator("#host-list-slot #host-section")).to_be_visible()
        await page.locator("#host-filter").select_option("updates")
        await expect(page.locator("#filter-count")).to_have_text("1")
        await page.locator("#host-search").fill("Alpha")
        await page.locator("#host-search").press("Enter")
        await expect(page.locator("#filter-count")).to_have_text("2")
        await page.locator("#selection-toggle").click()
        await expect(page.locator("#selection-panel")).to_contain_text(
            "Find host: Alpha"
        )
        await page.keyboard.press("Escape")
        await expect(page.locator("#selection-panel")).to_be_hidden()
        await page.locator("#reset-view").click()
        await expect(page.locator("#filter-count")).to_have_text("0")
        await expect(page.locator("#reset-view")).to_be_disabled()
        await page.locator(f'#hosts a.host-name[href="#/hosts/{first.id}"]').click()
        await expect(page.locator("#host-title")).to_have_text("Alpha node")
        await expect(page.locator("#host-info")).to_contain_text("6.8-synthetic")
        await expect(page.locator("#host-info")).to_contain_text("automation")
        await expect(page.locator("#host-info .restart-alert")).to_be_visible()
        await expect(
            page.locator("#host-info [data-delete-host] .button-icon")
        ).to_have_count(1)
        await expect(page.locator("#host-info .host-recent")).to_contain_text(
            "Check for updates"
        )
        await page.screenshot(
            path=f"/tmp/commander-host-workspace-{ingress}.png", full_page=True
        )
        await page.set_viewport_size({"width": 390, "height": 844})
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        await page.screenshot(
            path=f"/tmp/commander-host-workspace-mobile-{ingress}.png", full_page=True
        )
        await page.locator("#reset-view").click()
        await page.locator("#update-shown").click()
        await expect(page.locator("#confirm-accept")).to_be_disabled()
        await expect(page.locator("#confirm-targets")).to_contain_text(
            "Restart already required"
        )
        await page.locator("#confirm-ack").check()
        await expect(page.locator("#confirm-accept")).to_be_enabled()
        await page.locator("#confirm-cancel").click()
        assert await jobs.async_count(action=JobAction.UPDATE) == 0
        await page.locator("#update-shown").click()
        await expect(page.locator("#confirm-ack")).not_to_be_checked()
        await page.locator("#confirm-ack").check()
        await page.locator("#confirm-accept").click()
        await expect(page.locator("#message-text")).to_have_text("Updates queued")
        assert await jobs.async_count(action=JobAction.UPDATE) == 2
        assert await jobs.async_count(action=JobAction.REBOOT) == 0
        await page.goto(base + prefix + f"/#/jobs/{job.id}")
        await _wait_for_connection(page)
        await expect(page.locator("#job-result .job-restart-required")).to_be_visible()
        await expect(page.locator("#job-result .job-restart-required")).to_have_css(
            "color", "rgb(255, 210, 155)"
        )
        assert errors == []
        await browser.close()


async def test_old_active_jobs_keep_host_locked_beyond_recent_history(
    tmp_path: Path, socket_enabled: None
) -> None:
    """Active pagination, host counters and maintenance guards outlive history caps."""
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=True)
    app = create_app(
        settings,
        executor=FakeExecutor(),
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}),
    )
    async with (
        _live_server(_PrefixProxy(app, "/nested/active")) as base,
        async_playwright() as api,
    ):
        database = Database(settings.database_path)
        host = await HostRepository(database).async_create(
            HostCreate(
                name="Node 01", address="node-01.example.invalid", username="automation"
            )
        )
        await database.async_execute("UPDATE ui_preferences SET auto_check_enabled=0")
        await database.async_execute(
            "UPDATE hosts SET updates=2, checked_at=?",
            (datetime.now(UTC).isoformat(),),
        )
        jobs = JobRepository(database)
        running = await jobs.async_create(JobAction.UPDATE, host.id)
        await jobs.async_claim(running.id)
        # Insert queue records directly: no worker dispatch or remote execution.
        for _ in range(101):
            await jobs.async_create(JobAction.TEST_CONNECTION, host.id)
        for _ in range(101):
            recent = await jobs.async_create(JobAction.CHECK_UPDATES, host.id)
            await jobs.async_finish(
                recent.id,
                state=JobState.SUCCESS,
                output="Synthetic output",
                truncated=False,
                exit_code=0,
            )
        browser = await api.chromium.launch()
        page = await browser.new_page()
        await page.clock.install()
        await page.goto(base + f"/nested/active/#/hosts/{host.id}")
        await _wait_for_connection(page)
        await expect(page.locator("#dashboard")).to_contain_text("Running jobs1")
        await expect(page.locator("#dashboard")).to_contain_text("Queued jobs101")
        await expect(
            page.locator(f'[data-action="update"][data-host="{host.id}"]')
        ).to_be_disabled()
        await expect(
            page.locator(f'[data-action="reboot"][data-host="{host.id}"]')
        ).to_be_disabled()
        await page.goto(base + "/nested/active/#/hosts")
        await expect(page.locator("#update-shown")).to_have_text("Update all (0)")
        await expect(page.locator("#update-shown")).to_be_disabled()
        await database.async_execute(
            "UPDATE jobs SET state='success',finished_at=? "
            "WHERE state IN ('queued','running')",
            (datetime.now(UTC).isoformat(),),
        )
        await page.locator("#refresh").click()
        await expect(page.locator("#update-shown")).to_have_text("Update all (1)")
        await expect(page.locator("#update-shown")).to_be_enabled()
        await page.goto(base + f"/nested/active/#/hosts/{host.id}")
        await expect(page.locator("#dashboard")).to_contain_text("Running jobs0")
        await expect(page.locator("#dashboard")).to_contain_text("Queued jobs0")
        await expect(
            page.locator(f'[data-action="update"][data-host="{host.id}"]')
        ).to_be_enabled()
        await browser.close()
