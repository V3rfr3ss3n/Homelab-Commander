"""Interrupted mutation evidence remains visible in standalone and nested Ingress."""

from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect

from backend.homelab_backend.app import create_app
from backend.homelab_backend.config import Settings
from backend.homelab_backend.database import Database
from backend.homelab_backend.hosts import HostRepository
from backend.homelab_backend.jobs import JobRepository
from backend.homelab_backend.models import HostCreate, JobAction
from backend.tests.test_backend_api import TOKEN, FakeExecutor
from backend.tests.test_ui_browser import (
    _live_server,
    _PrefixProxy,
    _wait_for_connection,
)


@pytest.mark.parametrize("ingress", [False, True])
async def test_interrupted_update_is_visible_without_reexecution(
    tmp_path: Path, socket_enabled: None, ingress: bool
) -> None:
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=ingress)
    database = Database(settings.database_path)
    await database.async_migrate()
    host = await HostRepository(database).async_create(
        HostCreate(
            name="Node 01", address="node-01.example.invalid", username="automation"
        )
    )
    await database.async_execute("UPDATE ui_preferences SET auto_check_enabled=0")
    jobs = JobRepository(database)
    original = await jobs.async_create(JobAction.UPDATE, host.id, package_name="vim")
    await jobs.async_claim(original.id)
    executor = FakeExecutor()
    app = create_app(
        settings,
        executor=executor,
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}) if ingress else None,
    )
    prefix = "/nested/resource-jobs" if ingress else ""
    async with (
        _live_server(_PrefixProxy(app, prefix) if ingress else app) as base,
        async_playwright() as api,
    ):
        browser = await api.chromium.launch()
        page = await browser.new_page()
        await page.goto(base + prefix + f"/#/jobs/{original.id}")
        if not ingress:
            await page.locator("#token").fill(TOKEN)
            await page.locator("#connect").click()
        await _wait_for_connection(page)
        await expect(page.locator("#job-state-badge")).to_have_text("failed")
        await expect(page.locator("#job-result")).to_contain_text(
            "remote effects are uncertain"
        )
        await expect(page.locator("#review-job")).to_be_visible()
        await expect(page.locator("#log")).to_contain_text("Inspect the resource")
        await page.reload()
        await expect(page.locator("#job-state-badge")).to_have_text("failed")
        assert executor.calls == []
        assert await jobs.async_count() == 1
        persisted = await jobs.async_get(original.id)
        assert persisted.execution.scope.package_name == "vim"
        assert persisted.recovery_count == 1
        await browser.close()
