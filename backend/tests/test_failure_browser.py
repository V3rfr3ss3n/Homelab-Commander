"""History failures retain honest UI state and allow safe local diagnostics."""

import json
from pathlib import Path

import pytest
from playwright.async_api import Route, async_playwright, expect

from backend.homelab_backend.app import create_app
from backend.homelab_backend.config import Settings
from backend.homelab_backend.database import Database
from backend.homelab_backend.preview import PreviewExecutor, seed_demo
from backend.tests.test_backend_api import TOKEN
from backend.tests.test_ui_browser import (
    _live_server,
    _PrefixProxy,
    _wait_for_connection,
)


@pytest.mark.parametrize("ingress", [False, True])
async def test_history_failure_stale_data_details_and_recovery(
    tmp_path: Path, socket_enabled: None, ingress: bool
) -> None:
    # Reuse the actual versioned preview executor and seed, not a second mock UI.
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=ingress)
    executor = PreviewExecutor()
    app = create_app(
        settings,
        executor=executor,
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}) if ingress else None,
    )
    prefix = "/nested/failures" if ingress else ""

    async with (
        _live_server(_PrefixProxy(app, prefix) if ingress else app) as base,
        async_playwright() as api,
    ):
        await seed_demo(settings, executor)
        await Database(settings.database_path).async_execute(
            "UPDATE ui_preferences SET auto_check_enabled=0"
        )
        browser = await api.chromium.launch()
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        await context.grant_permissions(
            ["clipboard-read", "clipboard-write"], origin=base
        )
        page = await context.new_page()
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        await page.goto(base + prefix + "/")
        if not ingress:
            await page.locator("#token").fill(TOKEN)
            await page.locator("#connect").click()
        await _wait_for_connection(page)
        await expect(page.locator("#history-total")).to_have_text("14 jobs")
        failed = page.locator(".job-highlight").filter(
            has=page.get_by_text("Last failed job", exact=True)
        )
        await expect(failed.locator(".highlight-state")).to_have_text("failed")
        assert await failed.locator(".job-title").evaluate(
            "node=>getComputedStyle(node).color"
        ) == await page.evaluate(
            "()=>{const n=document.createElement('span');"
            "n.style.color='var(--danger)';document.body.append(n);"
            "const c=getComputedStyle(n).color;n.remove();return c}"
        )
        # A full offline refresh must mark cached history stale too, even if
        # the info/hosts request fails before the history request is attempted.
        await context.set_offline(True)
        await page.locator("#refresh").click()
        await expect(page.locator("#history-status")).to_contain_text("out of date")
        await expect(page.locator("#history-total")).to_have_text("14 jobs · stale")
        await context.set_offline(False)
        await page.locator("#history-retry").click()
        await expect(page.locator("#history-total")).to_have_text("14 jobs")
        mode = "http"

        async def fail(route: Route) -> None:
            if mode == "network":
                await route.abort()
            elif mode == "invalid":
                await route.fulfill(
                    status=200,
                    content_type="application/json",
                    body='{"total":14,"points":null}',
                )
            else:
                await route.fulfill(
                    status=500,
                    content_type="application/json",
                    headers={"X-Request-ID": "a" * 32},
                    body=json.dumps({"detail": "synthetic-private-response-secret"}),
                )

        await page.route("**/ui-api/jobs/timeline?**", fail)
        await page.locator("#refresh").click()
        await expect(page.locator("#history-status")).to_contain_text("out of date")
        await expect(page.locator("#history-total")).to_have_text("14 jobs · stale")
        await page.locator("#history-error-details").click()
        await page.locator("#error-details summary").click()
        await expect(page.locator("#error-diagnostic")).to_contain_text(
            '"error_code": "internal_error"'
        )
        await expect(page.locator("#error-diagnostic")).to_contain_text(
            '"request_id": "' + "a" * 32 + '"'
        )
        await page.locator("#copy-error-diagnostic").click()
        copied = await page.evaluate("navigator.clipboard.readText()")
        assert json.loads(copied)["http_status"] == 500
        for secret in (TOKEN, "synthetic-private-response-secret", "example.invalid"):
            assert secret not in copied
        await page.locator("#message-dismiss").click()
        # A new query must not relabel old data or claim there are zero jobs.
        await page.locator("#history-range").select_option("24h")
        await expect(page.locator("#history-total")).to_have_text("History unavailable")
        await expect(page.locator("#history-chart")).to_be_hidden()
        for failure_mode in ("network", "invalid"):
            mode = failure_mode
            await page.locator("#history-retry").click()
            await page.locator("#history-error-details").click()
            expected = "network_error" if mode == "network" else "invalid_response"
            await expect(page.locator("#error-diagnostic")).to_contain_text(expected)
            await page.locator("#message-dismiss").click()
        await page.unroute("**/ui-api/jobs/timeline?**", fail)
        await page.locator("#history-retry").click()
        await expect(page.locator("#history-status")).to_contain_text(
            "Job history refreshed."
        )
        await expect(page.locator("#history-chart")).to_be_visible()
        await page.locator("#history-range").select_option("7d")
        await expect(page.locator("#history-total")).to_have_text("14 jobs")
        await page.locator("#history-toggle").click()
        await expect(page.locator("#history-total")).to_have_text("14 jobs")
        await expect(page.locator("#jobs .row")).to_have_count(14)
        # Initial table failure on a fresh route also stays connected and explicit.
        await page.route("**/ui-api/jobs/page?**start=**", fail)
        await page.reload()
        await _wait_for_connection(page)
        await expect(page.locator("#history-total")).to_have_text("History unavailable")
        await expect(page.locator("#jobs-section")).to_be_hidden()
        await page.evaluate(
            "window.dispatchEvent(new PromiseRejectionEvent('unhandledrejection',"
            "{promise:Promise.resolve(),reason:new Error('synthetic-secret')}))"
        )
        await expect(page.locator("#error-diagnostic")).to_contain_text(
            "operation_failed"
        )
        assert "synthetic-secret" not in await page.locator("#message").inner_text()
        # A late navigation response must not dismiss a newer failure notice.
        await page.evaluate(
            "async()=>{let finish;const pending=run(null,()=>new Promise("
            "resolve=>finish=resolve));showFailure(new RequestFailure("
            "'http_503','GET jobs / timeline',503));finish();await pending}"
        )
        await expect(page.locator("#message-text")).to_contain_text(
            "temporarily unavailable"
        )
        assert not page_errors
        await page.screenshot(
            path=f"/tmp/commander-diagnostics-{ingress}.png", full_page=True
        )
        await browser.close()
