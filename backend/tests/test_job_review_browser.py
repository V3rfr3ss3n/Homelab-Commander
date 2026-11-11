"""A notice can be reviewed without deleting its history under either UI auth mode."""

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
async def test_notice_review_survives_reload(
    tmp_path: Path, socket_enabled: None, ingress: bool
):
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=ingress)
    app = create_app(
        settings,
        executor=FakeExecutor(),
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}) if ingress else None,
    )
    prefix = "/nested/review" if ingress else ""
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
        await database.async_execute(
            "UPDATE hosts SET checked_at=?", (datetime.now(UTC).isoformat(),)
        )
        await database.async_execute("UPDATE ui_preferences SET auto_check_enabled=0")
        jobs = JobRepository(database)
        failure = await jobs.async_create(JobAction.TEST_CONNECTION, host.id)
        await jobs.async_finish(
            failure.id,
            state=JobState.FAILED,
            output="Synthetic failure",
            truncated=False,
        )
        browser = await api.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 390, "height": 844})
        await page.goto(base + prefix + "/")
        if not ingress:
            await page.locator("#token").fill(TOKEN)
            await page.locator("#connect").click()
        await _wait_for_connection(page)
        marker = page.locator(f'#history a[href="#/jobs/{failure.id}"] circle')
        await expect(marker).to_have_css("fill", "rgb(237, 140, 152)")
        await page.locator(f'#notices a[href="#/jobs/{failure.id}"]').click()
        await page.get_by_role("button", name="Mark as reviewed").click()
        await expect(page.locator("#job-metadata")).to_contain_text("Reviewed")
        await expect(page.locator("#log")).to_have_text("Synthetic failure")
        await page.reload()
        await _wait_for_connection(page)
        await expect(page.locator("#job-metadata")).to_contain_text("Reviewed")
        await expect(page.get_by_role("button", name="Mark as reviewed")).to_have_count(
            0
        )
        await page.locator('nav a[data-tab="dashboard"]').click()
        await expect(page.locator("#notices-panel")).to_be_hidden()
        await expect(page.locator("#job-highlights")).to_contain_text("Last failed job")
        await expect(marker).not_to_have_css("fill", "rgb(237, 140, 152)")
        assert (await jobs.async_get(failure.id)).state == JobState.FAILED
        await browser.close()
