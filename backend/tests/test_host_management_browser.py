"""Host removal must not reload deleted details; edit actions remain easy to reach."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from playwright.async_api import async_playwright, expect

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
async def test_host_removal_returns_to_list_without_deleted_detail_requests(
    tmp_path: Path, socket_enabled: None, ingress: bool
) -> None:
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=ingress)
    executor = FakeExecutor()
    app = create_app(
        settings,
        executor=executor,
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}) if ingress else None,
    )
    prefix = "/nested/hosts" if ingress else ""
    async with (
        _live_server(_PrefixProxy(app, prefix) if ingress else app) as base,
        async_playwright() as api,
    ):
        database = Database(settings.database_path)
        await database.async_execute("UPDATE ui_preferences SET auto_check_enabled=0")
        hosts = HostRepository(database)
        host = await hosts.async_create(
            HostCreate(
                name="Node 01", address="node-01.example.invalid", username="automation"
            )
        )
        browser = await api.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 390, "height": 844})
        errors = []
        failed_requests = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "response",
            lambda response: (
                failed_requests.append(response.url) if response.status == 404 else None
            ),
        )
        await page.goto(base + prefix + f"/#/hosts/{host.id}")
        if not ingress:
            await page.locator("#token").fill(TOKEN)
            await page.locator("#connect").click()
        await _wait_for_connection(page)
        await expect(page.locator("#host-title")).to_have_text("Node 01")
        # Cancelling must not delete or navigate away.
        page.once("dialog", lambda dialog: dialog.dismiss())
        await page.locator("[data-delete-host]").click()
        assert await hosts.async_get(host.id) is not None
        await expect(page).to_have_url(base + prefix + f"/#/hosts/{host.id}")
        # Failed writes keep the user on the existing host, with a useful error.
        endpoint = f"**/ui-api/hosts/{host.id}"
        await page.route(
            endpoint,
            lambda route: route.fulfill(
                status=503, json={"detail": "Synthetic removal failure"}
            ),
        )
        page.once("dialog", lambda dialog: dialog.accept())
        await page.locator("[data-delete-host]").click()
        await expect(page.locator("#message")).to_have_text("Synthetic removal failure")
        assert await hosts.async_get(host.id) is not None
        await page.unroute(endpoint)
        page.once("dialog", lambda dialog: dialog.accept())
        with patch.object(executor, "async_execute", new_callable=AsyncMock) as execute:
            await page.locator("[data-delete-host]").click()
            await expect(page).to_have_url(base + prefix + "/#/hosts")
            await expect(page.locator("#message")).to_have_text("Host removed")
            await expect(page.locator("#hosts")).to_contain_text("No hosts to show")
            execute.assert_not_called()
        assert await hosts.async_get(host.id) is None
        assert errors == []
        assert failed_requests == []
        await page.reload()
        await _wait_for_connection(page)
        await expect(page.locator("#hosts")).to_contain_text("No hosts to show")
        await browser.close()


@pytest.mark.parametrize("ingress", [False, True])
async def test_edit_host_exposes_setup_copy_and_removal(
    tmp_path: Path, socket_enabled: None, ingress: bool
) -> None:
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=ingress)
    app = create_app(
        settings,
        executor=FakeExecutor(),
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}) if ingress else None,
    )
    prefix = "/nested/edit" if ingress else ""
    async with (
        _live_server(_PrefixProxy(app, prefix) if ingress else app) as base,
        async_playwright() as api,
    ):
        database = Database(settings.database_path)
        await database.async_execute("UPDATE ui_preferences SET auto_check_enabled=0")
        hosts = HostRepository(database)
        host = await hosts.async_create(
            HostCreate(
                name="Node 01",
                address="node-01.example.invalid",
                username="automation",
                port=2222,
            )
        )
        browser = await api.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 390, "height": 844})
        await context.grant_permissions(
            ["clipboard-read", "clipboard-write"], origin=base
        )
        page = await context.new_page()
        await page.goto(base + prefix + f"/#/hosts/{host.id}")
        if not ingress:
            await page.locator("#token").fill(TOKEN)
            await page.locator("#connect").click()
        await _wait_for_connection(page)
        await page.locator("[data-edit-host]").click()
        await expect(page.locator("#host-edit-actions")).to_be_visible()
        assert await page.locator("#host-edit-actions").evaluate(
            "actions => Boolean(actions.compareDocumentPosition("
            "document.getElementById('host-form')) & Node.DOCUMENT_POSITION_FOLLOWING)"
        )
        await page.locator("#host-name").fill("Edited Node")
        await page.locator("#host-address").fill("")
        await page.locator("#host-update-setup").click()
        await page.locator("#host-system-next").click()
        await expect(page.locator("#setup-mode")).to_have_value("update")
        await expect(page.locator("#copy-setup")).to_be_enabled()
        await page.locator("#copy-setup").click()
        await expect(page.locator("#setup-status")).to_have_text(
            "Script copied. Run it on the target as root."
        )
        command = await page.evaluate("navigator.clipboard.readText()")
        assert '"mode": "update"' in command
        assert '"port": 2222' in command
        await page.locator("#host-setup-next").click()
        await expect(page.locator("#host-name")).to_have_value("Edited Node")
        await expect(page.locator("#host-address")).to_have_value("")
        await expect(page.locator("#host-user")).to_have_value("automation")
        await expect(page.locator("#host-port")).to_have_value("2222")
        assert (await hosts.async_get(host.id)).name == "Node 01"
        page.once("dialog", lambda dialog: dialog.dismiss())
        await page.locator("#host-delete").click()
        await expect(page.locator("#host-dialog")).to_be_visible()
        assert await hosts.async_get(host.id) is not None
        endpoint = f"**/ui-api/hosts/{host.id}"
        await page.route(
            endpoint,
            lambda route: route.fulfill(
                status=503, json={"detail": "Synthetic removal failure"}
            ),
        )
        page.once("dialog", lambda dialog: dialog.accept())
        await page.locator("#host-delete").click()
        await expect(page.locator("#host-form-error")).to_have_text(
            "Synthetic removal failure"
        )
        await expect(page.locator("#host-dialog")).to_be_visible()
        assert await hosts.async_get(host.id) is not None
        await page.unroute(endpoint)
        messages = []

        async def confirm(dialog):
            messages.append(dialog.message)
            await dialog.accept()

        page.once("dialog", confirm)
        await page.locator("#host-delete").click()
        await expect(page.locator("#host-dialog")).not_to_be_visible()
        await expect(page).to_have_url(base + prefix + "/#/hosts")
        await expect(page.locator("#message")).to_have_text("Host removed")
        assert "Node 01" in messages[0]
        assert "SSH access" in messages[0]
        assert await hosts.async_get(host.id) is None
        await browser.close()
