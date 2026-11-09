"""User-facing dashboard and onboarding flows in standalone and Ingress."""

import json
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect

from backend.homelab_backend.app import create_app
from backend.homelab_backend.config import Settings
from backend.tests.test_backend_api import TOKEN, FakeExecutor
from backend.tests.test_ui_browser import (
    _accept_dialog,
    _live_server,
    _PrefixProxy,
    _wait_for_connection,
    _wait_for_message,
)


@pytest.mark.parametrize("ingress", [False, True])
async def test_dashboard_host_import_and_task_assignment(
    tmp_path: Path, socket_enabled: None, ingress: bool
) -> None:
    """Dialogs, filtered notices and guarded tasks work without leaking credentials."""
    app = create_app(
        Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=ingress),
        executor=FakeExecutor(),
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}) if ingress else None,
    )
    prefix = "/nested/ingress/synthetic" if ingress else ""
    server = _PrefixProxy(app, prefix) if ingress else app
    async with _live_server(server) as base_url, async_playwright() as api:
        browser = await api.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 390, "height": 844})
        await context.grant_permissions(
            ["clipboard-read", "clipboard-write"], origin=base_url
        )
        page = await context.new_page()
        await page.route(
            "**/ui-api/preferences/host-checks",
            lambda route: route.fulfill(json={"enabled": False}),
        )
        page.on("dialog", _accept_dialog)
        errors: list[str] = []
        console_errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "console",
            lambda msg: (
                console_errors.append(msg.text)
                if "Content Security Policy" in msg.text
                else None
            ),
        )
        await page.goto(base_url + prefix + "/")
        if not ingress:
            await page.locator("#token").fill(TOKEN)
            await page.locator("#connect").click()
        await _wait_for_connection(page)
        assert await page.locator("#dashboard").is_visible()
        await expect(page.locator("#connection-state")).to_be_hidden()
        await expect(page.locator("#message")).to_be_hidden()
        await expect(page.get_by_text("Backend online", exact=True)).to_have_count(1)
        await page.locator('nav a[href="#/tasks"]').click()
        await page.locator("#tasks").wait_for(state="visible")
        await expect(page.locator("#message")).to_be_hidden()
        await page.locator('nav a[href="#/dashboard"]').click()
        await page.locator("#dashboard").wait_for(state="visible")
        await expect(page.locator("#message")).to_be_hidden()
        await page.locator("#connect").click()
        await _wait_for_connection(page)
        await expect(page.locator("#message")).to_be_hidden()
        assert not await page.locator("#host-dialog").is_visible()
        assert not await page.locator("#task-dialog").is_visible()
        assert await page.locator("#history .graph-series.success circle").count() == 7
        await page.locator("[data-add-host]").click()
        await page.locator('[data-setup="debian"]').click()
        await _wait_for_message(page, "Setup command copied")
        assert "HLC_HOST_BEGIN" in await page.locator("#setup-preview").inner_text()
        assert "sudo python3" in await page.evaluate("navigator.clipboard.readText()")
        # Pasting and saving the versioned output never contact a host.
        envelope = {
            "format": "homelab-commander-host",
            "version": 1,
            "name": "Node 01",
            "username": "automation",
            "port": 2222,
            "addresses": ["node-01.example.invalid", "node-02.example.invalid"],
        }

        async def paste(value: str) -> None:
            await page.locator("#host-address").evaluate(
                "(field, text) => {const data = new DataTransfer();"
                "data.setData('text', text);field.dispatchEvent(new ClipboardEvent("
                "'paste', {clipboardData:data,bubbles:true,cancelable:true}));}",
                value,
            )

        await paste(json.dumps({**envelope, "version": 2}))
        assert "Unsupported" in await page.locator("#host-form-error").inner_text()
        await paste(json.dumps({**envelope, "port": 0}))
        assert "Invalid" in await page.locator("#host-form-error").inner_text()
        await paste("HLC_HOST_BEGIN\n" + json.dumps(envelope) + "\nHLC_HOST_END")
        assert await page.locator("#host-name").input_value() == "Node 01"
        assert await page.locator("#host-port").input_value() == "2222"
        assert await page.locator("#host-address").input_value() == ""
        await page.locator("#import-address").select_option("node-01.example.invalid")
        await page.locator("#host-form button[type=submit]").click()
        await _wait_for_message(page, "Host added")
        assert await page.locator("#hosts [data-action]").count() == 3
        await expect(page.locator("#hosts")).to_contain_text("Update status unknown")
        await expect(page.locator("#hosts")).not_to_contain_text("0 updates")
        await expect(page.locator("#hosts")).not_to_contain_text("reboot not required")
        await expect(page.locator("#dashboard .metric-detail").first).to_contain_text(
            "Update status unknown · 1 unchecked host"
        )
        assert await page.locator("#jobs").get_by_text("No jobs yet.").is_visible()
        await page.locator('a.notice[href="#/hosts?filter=stale"]').click()
        await expect(page.locator("#host-filter")).to_contain_text("Filter: stale")
        await page.get_by_role("link", name="Details", exact=True).click()
        await page.locator("#host-detail [data-add-task]").click()
        await page.locator("#task-name").fill("Read uptime")
        await page.locator("#task-argv").fill('["uptime"]')
        await page.locator("#task-distributions").fill("debian, ubuntu")
        await page.locator("#task-programs").fill("uptime")
        await page.locator("#task-form button[type=submit]").click()
        await _wait_for_message(page, "Task added")
        assert await page.locator("[data-assign-task]").is_disabled()
        assert await page.locator("#host-tasks [data-task]").is_disabled()
        await page.locator("[data-check-task]").click()
        await _wait_for_message(page, "Compatibility checked")
        await page.locator("[data-assign-task]").click()
        await _wait_for_message(page, "Assignment updated")
        await page.locator("#host-tasks [data-task]").click()
        await _wait_for_message(page, "Task queued")
        await page.locator("[data-assign-task]").click()
        await _wait_for_message(page, "Assignment updated")
        assert await page.locator("#host-tasks [data-task]").is_disabled()
        await page.locator("[data-unassign-task]").click()
        await _wait_for_message(page, "Task unassigned")
        await page.locator('nav a[href="#/tasks"]').click()
        await page.locator("#tasks [data-toggle-task]").click()
        await _wait_for_message(page, "Task updated")
        assert "Globally disabled" in await page.locator("#tasks").inner_text()
        await page.locator("#tasks [data-edit-task]").click()
        await page.locator("#task-description").fill("Updated synthetic description")
        await page.locator("#task-form button[type=submit]").click()
        await _wait_for_message(page, "Task updated")
        await page.locator('nav a[href="#/jobs"]').click()
        await page.locator("#job-state").select_option("success")
        await page.locator("#job-filters button").click()
        await page.locator("#jobs").get_by_text("success", exact=True).first.wait_for()
        assert "of 1" in await page.locator("#jobs-count").inner_text()
        await page.locator("#jobs [data-job-log]").first.click()
        await page.locator("#job-detail").wait_for(state="visible")
        assert "Custom task" in await page.locator("#job-metadata").inner_text()
        await page.reload()
        await _wait_for_connection(page)
        assert await page.locator("#job-detail").is_visible()
        await page.locator('nav a[href="#/dashboard"]').click()
        await expect(page.locator("#activity [data-job-log]")).to_have_count(1)
        assert await page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        )
        assert errors == []
        assert console_errors == []
        assert await page.evaluate("localStorage.length + sessionStorage.length") == 0
        await page.screenshot(
            path=f"/tmp/homelab-dashboard-{'ingress' if ingress else 'standalone'}.png",
            full_page=True,
        )
        await browser.close()
