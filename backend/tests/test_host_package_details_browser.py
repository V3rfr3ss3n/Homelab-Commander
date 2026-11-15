"""Browser coverage for the host package details dialog."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect

from backend.homelab_backend.app import create_app
from backend.homelab_backend.config import Settings
from backend.homelab_backend.database import Database
from backend.homelab_backend.hosts import HostRepository
from backend.homelab_backend.models import HostCreate
from backend.tests.test_backend_api import TOKEN
from backend.tests.test_packages import PackageExecutor
from backend.tests.test_ui_browser import _live_server, _wait_for_connection


@pytest.mark.parametrize("ingress", [False, True])
async def test_host_package_details_dialog(
    tmp_path: Path, socket_enabled: None, ingress: bool
) -> None:
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=ingress)
    app = create_app(
        settings,
        executor=PackageExecutor(),
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}) if ingress else None,
    )
    database = Database(settings.database_path)
    await database.async_migrate()
    hosts = HostRepository(database)
    ready = await hosts.async_create(
        HostCreate(
            name="Package node",
            address="node-package.example.invalid",
            username="automation",
        )
    )
    unchecked = await hosts.async_create(
        HostCreate(
            name="Unchecked node",
            address="node-unchecked.example.invalid",
            username="automation",
        )
    )
    empty = await hosts.async_create(
        HostCreate(
            name="Empty node",
            address="node-empty.example.invalid",
            username="automation",
        )
    )
    packages = [
        {
            "name": "curl",
            "old_version": "8.3.0-1",
            "new_version": "8.8.0-1",
            "is_security": False,
        },
        {
            "name": "openssl",
            "old_version": "3.0.1",
            "new_version": "3.0.2",
            "is_security": True,
        },
    ]
    checked_at = datetime.now(UTC).isoformat()
    await database.async_execute(
        "UPDATE hosts SET checked_at=?, updates=2, security_updates=1, "
        "packages_json=? WHERE id=?",
        (checked_at, json.dumps(packages), str(ready.id)),
    )
    await database.async_execute(
        "UPDATE hosts SET checked_at=?, updates=0, packages_json='[]' WHERE id=?",
        (checked_at, str(empty.id)),
    )
    await database.async_execute("UPDATE ui_preferences SET auto_check_enabled=0")
    prefix = "/nested/package-details" if ingress else ""
    from backend.tests.test_ui_browser import _PrefixProxy

    async with (
        _live_server(_PrefixProxy(app, prefix) if ingress else app) as base,
        async_playwright() as api,
    ):
        browser = await api.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(base + prefix + "/")
            if not ingress:
                await page.locator("#token").fill(TOKEN)
                await page.locator("#connect").click()
            await _wait_for_connection(page)
            await page.goto(base + prefix + f"/#/hosts/{ready.id}")
            metric = page.locator(".host-overview-metrics .host-metric").first
            toggle = metric.locator(".package-details-toggle")
            await expect(toggle).to_have_text("Package details (2)")
            await expect(page.locator("[data-security-filter]")).to_have_count(0)
            await toggle.click()
            dialog = page.locator("#package-dialog")
            await expect(dialog).to_be_visible()
            assert (
                "<time" not in await page.locator("#package-dialog-meta").inner_text()
            )
            await expect(page.locator("#package-dialog-meta time")).to_have_count(1)
            await page.locator("#package-skip-all").click()
            await expect(page.locator("#package-update-selected")).to_be_disabled()
            await expect(page.locator("#package-pending-count")).to_contain_text(
                "2 pending · 0"
            )
            await page.locator("#package-select-all").click()
            rows = dialog.locator(".package-row")
            await expect(rows).to_have_count(2)
            await expect(rows.nth(0)).to_contain_text("openssl")
            await expect(rows.nth(1)).to_contain_text("curl")
            openssl = rows.filter(has_text="openssl")
            curl = rows.filter(has_text="curl")
            await expect(openssl.locator(".security-count")).to_have_text("Security")
            await expect(curl.locator(".security-count")).to_have_count(0)
            for row, pkg_name in ((openssl, "openssl"), (curl, "curl")):
                await expect(row.locator('input[type="checkbox"]')).to_have_count(1)
                await expect(
                    row.locator('button[data-action="update-package"]')
                ).to_have_count(1)
                await expect(
                    row.locator(f'button[data-package="{pkg_name}"]')
                ).to_have_count(1)
            await page.locator("#package-sort").select_option(label="Name A-Z")
            await expect(rows.nth(0)).to_contain_text("curl")
            await openssl.locator('input[type="checkbox"]').check()
            await expect(openssl).to_have_class("package-row skipped")
            await page.locator("#package-sort").select_option("name-desc")
            await expect(openssl.locator("input")).to_be_checked()
            package_update = curl.locator('button[data-action="update-package"]')
            await package_update.click()
            await expect(page.locator("#confirm-title")).to_have_text(
                "Update only curl?"
            )
            async with page.expect_response(
                lambda response: (
                    response.request.method == "POST"
                    and response.url.endswith(
                        f"/ui-api/hosts/{ready.id}/actions/update"
                    )
                )
            ) as update_response:
                await page.locator("#confirm-ack").check()
                await page.locator("#confirm-accept").click()
            response = await update_response.value
            request = response.request
            assert json.loads(request.post_data or "{}") == {"package_name": "curl"}
            assert response.status == 202
            assert (await response.json())["package_name"] == "curl"
            await expect(rows).to_have_count(1)
            await expect(rows.first).to_contain_text("openssl")
            await expect(page.locator("#package-pending-count")).to_contain_text(
                "1 pending"
            )
            await expect(toggle).to_have_text("Package details (1)")
            await dialog.locator("[data-close-dialog]").click()

            await page.goto(base + prefix + f"/#/hosts/{unchecked.id}")
            await page.locator(".package-details-toggle").click()
            await expect(page.locator("#package-dialog")).to_be_visible()
            await expect(page.locator("#package-dialog")).to_contain_text(
                "Run a check to see package details."
            )
            await page.locator("#package-dialog [data-close-dialog]").click()

            await page.goto(base + prefix + f"/#/hosts/{empty.id}")
            await page.locator(".package-details-toggle").click()
            await expect(page.locator("#package-dialog")).to_be_visible()
            await expect(page.locator("#package-dialog")).to_contain_text(
                "No packages need updates."
            )
            await expect(page.locator("[data-security-filter]")).to_have_count(0)
        finally:
            await browser.close()


@pytest.mark.parametrize("mode", ["selected", "all", "failure"])
async def test_package_bulk_jobs_keep_counts_until_verified(
    tmp_path: Path, socket_enabled: None, mode: str
) -> None:
    executor = PackageExecutor()
    executor.release.clear()
    executor.fail = mode == "failure"
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=True)
    app = create_app(
        settings,
        executor=executor,
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}),
    )
    from backend.tests.test_ui_browser import _PrefixProxy

    async with (
        _live_server(_PrefixProxy(app, "/nested/packages")) as base,
        async_playwright() as api,
    ):
        database = Database(settings.database_path)
        host = await HostRepository(database).async_create(
            HostCreate(
                name="Node 01", address="node-01.example.invalid", username="automation"
            )
        )
        await database.async_execute("UPDATE ui_preferences SET auto_check_enabled=0")
        packages = [
            {"name": name, "old_version": "1", "new_version": "2", "is_security": False}
            for name in ("curl", "git")
        ]
        await database.async_execute(
            "UPDATE hosts SET checked_at=?,updates=2,packages_json=? WHERE id=?",
            (datetime.now(UTC).isoformat(), json.dumps(packages), str(host.id)),
        )
        browser = await api.chromium.launch()
        page = await browser.new_page(viewport={"width": 390, "height": 844})
        await page.clock.install()
        try:
            await page.goto(base + f"/nested/packages/#/hosts/{host.id}")
            await _wait_for_connection(page)
            await page.locator(".package-details-toggle").click()
            await page.locator("#package-skip-all").click()
            await expect(page.locator("#package-update-selected")).to_be_disabled()
            await page.locator("#package-select-all").click()
            async with page.expect_response(
                lambda r: (
                    r.request.method == "POST" and r.url.endswith("/actions/update")
                )
            ) as posted:
                await page.locator(
                    "#package-update-all"
                    if mode == "all"
                    else "#package-update-selected"
                ).click()
                await page.locator("#confirm-ack").check()
                await page.locator("#confirm-accept").click()
            response = await posted.value
            body = json.loads(response.request.post_data or "null")
            assert (
                body is None
                if mode == "all"
                else body == {"package_names": ["curl", "git"]}
            )
            await executor.started.wait()
            await expect(page.locator(".package-details-toggle")).to_have_text(
                "Package details (2)"
            )
            await expect(page.locator("#package-dialog .package-row")).to_have_count(2)
            await expect(page.locator("#package-update-selected")).to_be_disabled()
            executor.release.set()
            async with page.expect_response("**/ui-api/hosts/*/packages"):
                await page.clock.run_for(1600)
            remaining = 2 if mode == "failure" else 0
            await expect(page.locator("#package-dialog .package-row")).to_have_count(
                remaining
            )
            await expect(page.locator(".package-details-toggle")).to_have_text(
                f"Package details ({remaining})"
            )
            await expect(page.locator("#package-pending-count")).to_contain_text(
                f"{remaining} pending"
            )
            if mode == "selected":
                job_id = (await response.json())["id"]
                await page.locator("#package-dialog [data-close-dialog]").click()
                await page.goto(base + f"/nested/packages/#/jobs/{job_id}")
                await _wait_for_connection(page)
                await page.locator("#rerun-job").click()
                await expect(page.locator("#confirm-targets")).to_contain_text("curl")
                await expect(page.locator("#confirm-targets")).to_contain_text("git")
                async with page.expect_response(
                    lambda r: (
                        r.request.method == "POST" and r.url.endswith("/actions/update")
                    )
                ) as rerun:
                    await page.locator("#confirm-accept").click()
                assert json.loads((await rerun.value).request.post_data or "{}") == {
                    "package_names": ["curl", "git"]
                }
            assert await page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            )
        finally:
            executor.release.set()
            await browser.close()
