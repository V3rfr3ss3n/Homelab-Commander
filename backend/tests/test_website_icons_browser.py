"""Website icons survive refreshes and support modern HTTPS paths without TLS bypass."""

import re
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect

from backend.homelab_backend.app import create_app
from backend.homelab_backend.config import Settings
from backend.homelab_backend.database import Database
from backend.homelab_backend.hosts import HostRepository
from backend.homelab_backend.models import HostCreate, HostWebsite
from backend.tests.test_backend_api import TOKEN, FakeExecutor
from backend.tests.test_ui_browser import (
    _live_server,
    _PrefixProxy,
    _wait_for_connection,
)

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
    '<circle cx="8" cy="8" r="7" fill="green"/></svg>'
)


@pytest.mark.parametrize("ingress", [False, True])
async def test_icons_keep_nodes_and_failures_stable_between_refreshes(
    tmp_path: Path, socket_enabled: None, ingress: bool
) -> None:
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=ingress)
    app = create_app(
        settings,
        executor=FakeExecutor(),
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}) if ingress else None,
    )
    prefix = "/nested/icons" if ingress else ""
    async with (
        _live_server(_PrefixProxy(app, prefix) if ingress else app) as base,
        async_playwright() as api,
    ):
        db = Database(settings.database_path)
        await db.async_execute("UPDATE ui_preferences SET auto_check_enabled=0")
        await HostRepository(db).async_create(
            HostCreate(
                name="Node 01",
                address="node-01.example.invalid",
                username="automation",
                websites=(
                    HostWebsite(
                        name="TLS portal", url="https://tls.example.invalid/app"
                    ),
                    HostWebsite(
                        name="Plain portal", url="http://plain.example.invalid/app"
                    ),
                    HostWebsite(
                        name="Blocked portal", url="https://blocked.example.invalid/app"
                    ),
                    HostWebsite(
                        name="Custom portal",
                        url="https://custom.example.invalid/app",
                        icon_url="https://assets.example.invalid/portal.svg",
                    ),
                    HostWebsite(
                        name="TLS duplicate", url="https://tls.example.invalid/app"
                    ),
                ),
            )
        )
        browser = await api.chromium.launch(headless=True)
        page = await browser.new_page()
        requests = []

        async def website(route):
            requests.append(route.request)
            if route.request.url in {
                "https://tls.example.invalid/favicon.svg",
                "http://plain.example.invalid/favicon.ico",
                "https://assets.example.invalid/portal.svg",
            }:
                await route.fulfill(
                    content_type="image/svg+xml",
                    body=SVG,
                    headers={"Cache-Control": "no-store"},
                )
            elif "blocked.example.invalid" in route.request.url:
                await route.abort("failed")
            else:
                await route.fulfill(status=404, body="No icon")

        await page.route("**/*.example.invalid/**", website)
        await page.goto(base + prefix + "/")
        if not ingress:
            await page.locator("#token").fill(TOKEN)
            await page.locator("#connect").click()
        await _wait_for_connection(page)
        tls = page.get_by_role("link", name="Open TLS portal", exact=True)
        blocked = page.get_by_role("link", name="Open Blocked portal", exact=True)
        await expect(tls).to_have_attribute("data-icon-status", "loaded")
        await expect(blocked).to_have_attribute("data-icon-status", "unavailable")
        await expect(blocked).to_contain_text("B")
        await expect(blocked).to_have_attribute(
            "title", re.compile(r"Icon unavailable")
        )
        await expect(
            page.get_by_role("link", name="Open Custom portal", exact=True)
        ).to_have_attribute("data-icon-status", "loaded")
        await expect(
            page.get_by_role("link", name="Open TLS duplicate", exact=True)
        ).to_have_attribute("data-icon-status", "loaded")
        await page.evaluate(
            "window.originalIcon=document.querySelector('.website-icon img')"
        )
        count = len(requests)
        for _ in range(3):
            await page.locator("#refresh").click()
            await _wait_for_connection(page)
        assert await page.evaluate(
            "window.originalIcon===document.querySelector('.website-icon img')"
        )
        assert len(requests) == count
        await page.get_by_role("link", name="Details", exact=True).click()
        await expect(page.locator("#host-detail")).to_be_visible()
        await expect(page.locator("#host-info .website-icon").first).to_have_attribute(
            "data-icon-status", "loaded"
        )
        assert len(requests) == count
        await page.locator('nav a[data-tab="hosts"]').click()
        await expect(page.locator("#host-info .website-icon").first).to_have_attribute(
            "data-icon-status", "loaded"
        )
        assert len(requests) == count
        await page.locator("[data-edit-host]").click()
        assert (
            " | https://assets.example.invalid/portal.svg"
            in await page.locator("#host-websites").input_value()
        )
        await page.locator("#host-retry-icons").click()
        await expect(page.locator("#host-info .website-icon").nth(2)).to_have_attribute(
            "data-icon-status", "unavailable"
        )
        await expect(page.locator("#host-info .website-icon").first).to_have_attribute(
            "data-icon-status", "loaded"
        )
        assert len(requests) > count
        await expect(page.locator("#website-icon-status")).to_contain_text(
            "Retrying saved"
        )
        await page.locator("#host-websites").fill(
            "TLS portal | https://tls.example.invalid/app | javascript:alert(1)"
        )
        await page.locator("#host-form button[type=submit]").click()
        await expect(page.locator("#host-form-error")).to_contain_text("HTTP(S)")
        await page.locator("#host-websites").fill(
            "TLS portal | https://tls.example.invalid/app | https://assets.example.invalid/portal.svg"
        )
        await page.locator("#host-form button[type=submit]").click()
        await expect(page.locator("#host-dialog")).not_to_be_visible()
        await expect(page.locator("#host-info .website-icon")).to_have_count(1)
        await expect(page.locator("#host-info .website-icon")).to_have_attribute(
            "data-icon-status", "loaded"
        )
        assert all(
            "x-csrf-token" not in request.headers
            and "authorization" not in request.headers
            and "referer" not in request.headers
            for request in requests
        )
        assert not any(
            request.url.startswith("http://tls.")
            or request.url.startswith("http://blocked.")
            for request in requests
        )
        if not ingress:
            previous = len(requests)
            await page.locator("#disconnect").click()
            await expect(page.locator(".website-icon")).to_have_count(0)
            await page.locator("#token").fill(TOKEN)
            await page.locator("#connect").click()
            await _wait_for_connection(page)
            await expect(page.locator("#host-info .website-icon")).to_have_attribute(
                "data-icon-status", "loaded"
            )
            assert len(requests) > previous
        await browser.close()
