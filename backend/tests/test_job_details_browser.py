"""Job inspection, redacted log tools and deliberate reruns in both UI modes."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect

from backend.homelab_backend.app import create_app
from backend.homelab_backend.config import Settings
from backend.homelab_backend.custom_tasks import CustomTaskRepository
from backend.homelab_backend.database import Database
from backend.homelab_backend.hosts import HostRepository
from backend.homelab_backend.jobs import JobRepository
from backend.homelab_backend.models import (
    CustomTaskCreate,
    HostCreate,
    JobAction,
    JobState,
)
from backend.tests.test_backend_api import TOKEN, FakeExecutor
from backend.tests.test_ui_browser import (
    _live_server,
    _PrefixProxy,
    _wait_for_connection,
)


@pytest.mark.parametrize("ingress", [False, True])
async def test_job_workspace_log_tools_and_confirmed_rerun(
    tmp_path: Path, socket_enabled: None, ingress: bool
) -> None:
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=ingress)
    app = create_app(
        settings,
        executor=FakeExecutor(),
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}) if ingress else None,
    )
    prefix = "/nested/job-details" if ingress else ""
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
        jobs = JobRepository(database)
        job = await jobs.async_create(JobAction.TEST_CONNECTION, host.id)
        await jobs.async_claim(job.id)
        output = (
            "Synthetic check\nERROR: first issue\n"
            "<script>literal text</script>\nerror: second issue"
        )
        await jobs.async_finish(
            job.id,
            state=JobState.FAILED,
            output=output,
            truncated=True,
            exit_code=1,
            error_code="sudo_unavailable",
        )
        browser = await api.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 1440, "height": 1050}, timezone_id="UTC"
        )
        await context.grant_permissions(
            ["clipboard-read", "clipboard-write"], origin=base
        )
        page = await context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(base + prefix + f"/#/jobs/{job.id}")
        if not ingress:
            await page.locator("#token").fill(TOKEN)
            await page.locator("#connect").click()
        await _wait_for_connection(page)
        await expect(page.locator("#job-metadata h2")).to_have_text(
            "Connection test · Node 01"
        )
        assert await page.locator(".job-workspace-toolbar #copy-job-log").count() == 1
        assert (
            await page.locator(".job-workspace-toolbar #download-job-log").count() == 1
        )
        await expect(page.locator("#review-job")).to_be_visible()
        await expect(page.locator("#job-result")).to_contain_text(
            "Non-interactive sudo"
        )
        await expect(page.locator("#job-timeline li")).to_have_count(3)
        await expect(page.locator("#log")).to_have_text(output)
        await expect(page.locator("#job-log-note")).to_contain_text("truncated")
        assert await page.locator("#log script").count() == 0
        await page.locator("#job-log-search").fill("ERROR")
        await expect(page.locator("#job-log-matches")).to_have_text("1 of 2 matches")
        await page.locator("#job-log-next").click()
        await expect(page.locator("#job-log-matches")).to_have_text("2 of 2 matches")
        await page.locator("#copy-job-log").click()
        assert await page.evaluate("navigator.clipboard.readText()") == output
        await page.locator("#copy-job-link").click()
        assert await page.evaluate("navigator.clipboard.readText()") == page.url
        async with page.expect_download() as download_event:
            await page.locator("#download-job-log").click()
        download = await download_event.value
        destination = tmp_path / "downloaded-log.txt"
        await download.save_as(destination)
        assert destination.read_text() == output
        await expect(page.locator("#job-host-link")).to_have_attribute(
            "href", f"#/hosts/{host.id}"
        )
        await page.locator("#job-log-search").fill("")
        await page.screenshot(
            path=f"/tmp/commander-job-details-desktop-{ingress}.png", full_page=True
        )
        await page.get_by_role("button", name="Mark as reviewed", exact=True).click()
        await expect(page.locator("#job-metadata")).to_contain_text("Reviewed")
        await page.locator("#rerun-job").click()
        await expect(page.locator("#confirm-dialog")).to_contain_text("Node 01")
        await page.locator("#confirm-cancel").click()
        assert await jobs.async_count() == 1
        await page.locator("#rerun-job").click()
        await page.locator("#confirm-accept").click()
        await expect(page.locator("#message-text")).to_have_text("New job queued")
        assert await jobs.async_count() == 2
        assert (await jobs.async_get(job.id)).state == JobState.FAILED
        await page.set_viewport_size({"width": 390, "height": 844})
        search_box = await page.locator("#job-log-search").bounding_box()
        assert search_box is not None
        assert search_box["width"] >= 150
        await page.screenshot(
            path=f"/tmp/commander-job-details-mobile-{ingress}.png", full_page=True
        )
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert errors == []
        await browser.close()


async def test_job_detail_refresh_ignores_recent_list_and_handles_log_error(
    tmp_path: Path, socket_enabled: None
) -> None:
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=True)
    app = create_app(
        settings,
        executor=FakeExecutor(),
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}),
    )
    async with (
        _live_server(_PrefixProxy(app, "/nested/live-job")) as base,
        async_playwright() as api,
    ):
        database = Database(settings.database_path)
        host = await HostRepository(database).async_create(
            HostCreate(
                name="Node 01", address="node-01.example.invalid", username="automation"
            )
        )
        await database.async_execute("UPDATE ui_preferences SET auto_check_enabled=0")
        jobs = JobRepository(database)
        job = await jobs.async_create(JobAction.TEST_CONNECTION, host.id)
        await jobs.async_claim(job.id)
        browser = await api.chromium.launch()
        page = await browser.new_page()
        await page.clock.install()
        await page.route("**/ui-api/jobs", lambda route: route.fulfill(json=[]))
        await page.goto(base + f"/nested/live-job/#/jobs/{job.id}")
        await _wait_for_connection(page)
        await expect(page.locator("#job-state-badge")).to_have_text("running")
        await expect(page.locator("#rerun-job")).to_be_disabled()
        await jobs.async_finish(
            job.id,
            state=JobState.SUCCESS,
            output="Finished",
            truncated=False,
            exit_code=0,
        )
        async with page.expect_response(f"**/ui-api/jobs/{job.id}"):
            await page.clock.run_for(1600)
        await expect(page.locator("#job-state-badge")).to_have_text("success")
        await expect(page.locator("#log")).to_have_text("Finished")
        await page.route(
            f"**/ui-api/jobs/{job.id}/log",
            lambda route: route.fulfill(
                status=503, json={"detail": "Synthetic log unavailable"}
            ),
        )
        await page.locator("#refresh-job").click()
        await expect(page.locator("#job-log-note")).to_contain_text(
            "Synthetic log unavailable"
        )
        await expect(page.locator("#job-state-badge")).to_have_text("success")
        await page.unroute(f"**/ui-api/jobs/{job.id}/log")
        await page.locator("#refresh-job").click()
        await expect(page.locator("#log")).to_have_text("Finished")
        await page.evaluate(
            "location.hash='/jobs/00000000-0000-4000-8000-000000000099'"
        )
        await expect(page.locator("#job-metadata")).to_contain_text("Job not found")
        await expect(page.locator("#log")).to_have_text("")
        await expect(page.locator("#copy-job-log")).to_be_disabled()
        await browser.close()


async def test_custom_task_name_and_missing_assignment_block_rerun(
    tmp_path: Path, socket_enabled: None
) -> None:
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=True)
    app = create_app(
        settings,
        executor=FakeExecutor(),
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}),
    )
    async with (
        _live_server(_PrefixProxy(app, "/nested/task-job")) as base,
        async_playwright() as api,
    ):
        database = Database(settings.database_path)
        host = await HostRepository(database).async_create(
            HostCreate(
                name="Node 01", address="node-01.example.invalid", username="automation"
            )
        )
        await database.async_execute("UPDATE ui_preferences SET auto_check_enabled=0")
        task = await CustomTaskRepository(database, allow_shell=False).async_create(
            CustomTaskCreate(name="Inspect service health", argv=("uptime",))
        )
        jobs = JobRepository(database)
        job = await jobs.async_create(
            JobAction.CUSTOM_TASK, host.id, custom_task_id=task.id
        )
        await jobs.async_claim(job.id)
        await jobs.async_finish(
            job.id,
            state=JobState.SUCCESS,
            output="Synthetic health check completed.",
            truncated=False,
            exit_code=0,
        )
        browser = await api.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1050})
        await page.goto(base + f"/nested/task-job/#/jobs/{job.id}")
        await _wait_for_connection(page)
        await expect(page.locator("#job-metadata h2")).to_have_text(
            "Inspect service health · Node 01"
        )
        await expect(page.locator("#rerun-job")).to_be_disabled()
        await expect(page.locator("#job-rerun-note")).to_contain_text("assignment")
        await expect(
            page.get_by_role("link", name="Review host tasks")
        ).to_have_attribute("href", f"#/tasks?host_id={host.id}")
        assert await jobs.async_count() == 1
        await page.screenshot(
            path="/tmp/commander-job-details-success.png", full_page=True
        )
        await browser.close()


@pytest.mark.parametrize("locale", ["en-US", "de-DE"])
async def test_job_duration_units_and_precise_lifecycle_times(
    tmp_path: Path, socket_enabled: None, locale: str
) -> None:
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=True)
    app = create_app(
        settings,
        executor=FakeExecutor(),
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}),
    )
    async with (
        _live_server(_PrefixProxy(app, "/nested/timing")) as base,
        async_playwright() as api,
    ):
        database = Database(settings.database_path)
        host = await HostRepository(database).async_create(
            HostCreate(
                name="Node 01", address="node-01.example.invalid", username="automation"
            )
        )
        await database.async_execute("UPDATE ui_preferences SET auto_check_enabled=0")
        jobs = JobRepository(database)
        job = await jobs.async_create(JobAction.CHECK_UPDATES, host.id)
        await jobs.async_finish(
            job.id,
            state=JobState.SUCCESS,
            output="Synthetic output",
            truncated=False,
            exit_code=0,
        )
        browser = await api.chromium.launch()
        page = await browser.new_page(timezone_id="UTC", locale=locale)
        decimal = "," if locale == "de-DE" else "."
        start = datetime(2026, 11, 11, 10, 0, 0, 123000, tzinfo=UTC)
        for index, (seconds, expected) in enumerate([
            (0.0002, "<1 ms"),
            (0.0087, f"8{decimal}7 ms"),
            (1.234, f"1{decimal}23 s"),
            (62.125, "1 min 2 s"),
            (3601, "1 h 0 min 1 s"),
        ]):
            await database.async_execute(
                "UPDATE jobs SET created_at=?,started_at=?,finished_at=? WHERE id=?",
                (
                    (start - timedelta(milliseconds=20)).isoformat(),
                    start.isoformat(),
                    (start + timedelta(seconds=seconds)).isoformat(),
                    str(job.id),
                ),
            )
            if index == 0:
                await page.goto(base + f"/nested/timing/#/jobs/{job.id}")
                await _wait_for_connection(page)
            else:
                await page.locator("#refresh-job").click()
            await expect(page.locator("#job-duration")).to_have_text(expected)
            await expect(page.locator("#job-timeline li").nth(1)).to_contain_text(
                f"10:00:00{decimal}123"
            )
            await expect(page.locator("#job-timeline li").nth(1)).to_contain_text("UTC")
            started = page.locator("#job-timeline li").nth(1).locator("time")
            timestamp = start.isoformat().replace("+00:00", "Z")
            await expect(started).to_have_attribute("datetime", timestamp)
            await expect(started).to_have_attribute("title", timestamp)
            await expect(started.locator(".job-date")).to_have_text(
                "11.11.2026" if locale == "de-DE" else "Nov 11, 2026"
            )
            await expect(page.locator("#review-job")).to_be_hidden()
            await expect(page.locator("#job-metadata h2")).to_have_text(
                "Check for updates · Node 01"
            )
        await browser.close()
