"""The actual VS Code/CLI preview must obey the package snapshot contract."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from playwright.async_api import async_playwright, expect

from backend.homelab_backend.automation import AnsibleExecutor, HostSnapshot
from backend.homelab_backend.database import Database
from backend.homelab_backend.models import JobAction, PackageInfo
from backend.homelab_backend.preview import (
    PreviewExecutor,
    create_preview,
    demo_packages,
    main,
)
from backend.tests.test_automation import _host
from backend.tests.test_backend_api import _csrf
from backend.tests.test_ui_browser import _live_server, _wait_for_connection


def terminal(client: TestClient, job_id: str) -> dict[str, object]:
    async def wait() -> dict[str, object]:
        async with asyncio.timeout(10):
            while True:
                response = await asyncio.to_thread(client.get, f"/ui-api/jobs/{job_id}")
                result = response.json()
                if result["state"] in ("success", "failed"):
                    return result  # type: ignore[no-any-return]

    assert client.portal is not None
    return client.portal.call(wait)


@pytest.mark.parametrize(
    ("scope", "remaining", "security"),
    [
        ({"package_name": "vim"}, 11, 3),
        ({"package_names": ["vim", "curl"]}, 10, 2),
        (None, 0, 0),
    ],
)
def test_real_preview_updates_and_checks_preserve_remaining_packages(
    tmp_path: Path, scope: dict[str, object] | None, remaining: int, security: int
) -> None:
    with (
        patch.object(
            AnsibleExecutor,
            "async_execute",
            side_effect=AssertionError("Real executor forbidden"),
        ),
        TestClient(create_preview(tmp_path), client=("127.0.0.1", 12345)) as client,
    ):
        host = client.get("/ui-api/hosts").json()[0]
        assert host["updates"] == 12
        csrf = {"X-CSRF-Token": _csrf(client)}
        response = client.post(
            f"/ui-api/hosts/{host['id']}/actions/update", json=scope, headers=csrf
        )
        assert response.status_code == 202
        assert terminal(client, response.json()["id"])["state"] == "success"
        for check in (False, True):
            if check:
                queued = client.post(
                    f"/ui-api/hosts/{host['id']}/actions/check_updates", headers=csrf
                ).json()
                assert terminal(client, queued["id"])["state"] == "success"
            packages = client.get(f"/ui-api/hosts/{host['id']}/packages").json()
            current = next(
                h for h in client.get("/ui-api/hosts").json() if h["id"] == host["id"]
            )
            assert packages["total"] == current["updates"] == remaining
            assert (
                packages["security_updates"] == current["security_updates"] == security
            )
            assert len(packages["packages"]) == remaining
            assert all(p["name"] != "vim" for p in packages["packages"])
        tasks = client.get("/ui-api/custom-tasks").json()
        job = client.post(
            f"/ui-api/hosts/{host['id']}/tasks/{tasks[0]['id']}", headers=csrf
        )
        assert job.status_code == 202
        assert terminal(client, job.json()["id"])["state"] == "success"
        reboot = client.post(f"/ui-api/hosts/{host['id']}/actions/reboot", headers=csrf)
        assert terminal(client, reboot.json()["id"])["state"] == "success"
        assert not next(
            h for h in client.get("/ui-api/hosts").json() if h["id"] == host["id"]
        )["reboot_required"]


@pytest.mark.parametrize(
    ("updates", "security", "packages"),
    [
        (0, 0, demo_packages(12, 4)),
        (1, 2, ()),
        (1, 0, demo_packages(1, 1)),
        (-1, 0, ()),
    ],
)
def test_contradictory_adapter_snapshot_cannot_clear_stored_status(
    updates: int, security: int, packages: tuple[PackageInfo, ...]
) -> None:
    with pytest.raises(ValueError, match="snapshot counts"):
        HostSnapshot(
            distribution="Debian",
            distribution_version="12",
            kernel="synthetic",
            updates=updates,
            security_updates=security,
            reboot_required=False,
            status="ok",
            checked_at=datetime.now(UTC),
            packages=packages,
        )


def test_preview_entrypoint_binds_loopback_and_disables_proxy_trust() -> None:
    with patch("uvicorn.run") as run:
        main([])
    assert run.call_args.kwargs["host"] == "127.0.0.1"
    assert run.call_args.kwargs["port"] == 8100
    assert run.call_args.kwargs["proxy_headers"] is False
    assert run.call_args.kwargs["access_log"] is False


def test_preview_history_failure_once_recovers_without_losing_jobs(
    tmp_path: Path,
) -> None:
    with TestClient(
        create_preview(tmp_path, history_failure_once=True),
        client=("127.0.0.1", 50000),
    ) as client:
        now = datetime.now(UTC)
        params = {
            "start": (now - timedelta(days=7)).isoformat(),
            "end": now.isoformat(),
        }
        assert client.get("/ui-api/jobs/page").status_code == 200
        failed = client.get("/ui-api/jobs/timeline", params=params)
        assert failed.status_code == 503
        assert len(failed.headers["X-Request-ID"]) == 32
        recovered = client.get("/ui-api/jobs/timeline", params=params)
        assert recovered.status_code == 200
        assert recovered.json()["total"] == 14
        assert client.get("/ui-api/jobs/page", params=params).json()["total"] == 14


async def test_preview_vim_update_and_package_toolbar_on_desktop_and_mobile(
    tmp_path: Path, socket_enabled: None
) -> None:
    async with (
        _live_server(create_preview(tmp_path)) as base,
        async_playwright() as api,
    ):
        await Database(tmp_path / "homelab_updates.db").async_execute(
            "UPDATE ui_preferences SET auto_check_enabled=0"
        )
        browser = await api.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        await page.clock.install()
        await page.goto(base)
        await _wait_for_connection(page)
        await page.locator("#hosts .host-name").first.click()
        await page.locator(".package-details-toggle").click()
        await expect(page.locator("#package-pending-count")).to_contain_text(
            "12 pending"
        )
        sort = await page.locator("#package-sort").bounding_box()
        selection = await page.get_by_role(
            "group", name="Package selection"
        ).bounding_box()
        primary = await page.locator("#package-update-selected").bounding_box()
        assert sort is not None
        assert selection is not None
        assert primary is not None
        assert selection["x"] > sort["x"] + sort["width"]
        assert primary["y"] > sort["y"] + sort["height"]
        await expect(
            page.locator("#package-update-selected .button-icon")
        ).to_have_count(1)
        await page.screenshot(path="/tmp/dev5-package-toolbar-desktop.png")
        vim = page.locator("#package-dialog .package-row").filter(
            has=page.get_by_text("vim", exact=True)
        )
        await vim.get_by_role("button", name="Update", exact=True).click()
        await page.locator("#confirm-ack").check()
        await page.locator("#confirm-accept").click()
        await page.clock.run_for(1600)
        await expect(page.locator("#package-pending-count")).to_contain_text(
            "11 pending"
        )
        await expect(page.locator("#package-dialog .package-row")).to_have_count(11)
        await expect(vim).to_have_count(0)
        await expect(page.locator(".package-details-toggle")).to_have_text(
            "Package details (11)"
        )
        async with page.expect_response("**/ui-api/hosts/*/packages"):
            await page.locator("#package-check").click()
        await expect(page.locator("#package-pending-count")).to_contain_text(
            "11 pending"
        )
        await page.set_viewport_size({"width": 390, "height": 844})
        await expect(page.locator("#package-update-selected")).to_be_in_viewport()
        await expect(page.locator("#package-update-all")).to_be_in_viewport()
        assert await page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        assert await page.locator("#package-dialog").evaluate(
            "(d)=>d.scrollHeight<=d.clientHeight"
        )
        await page.screenshot(path="/tmp/dev5-package-toolbar-mobile.png")
        await browser.close()


async def test_preview_checks_never_resurrect_packages_from_stale_inventory() -> None:
    host = _host().model_copy(
        update={
            "packages": demo_packages(12, 4),
            "updates": 12,
            "security_updates": 4,
            "reboot_required": True,
        }
    )
    executor = PreviewExecutor()
    first = await executor.async_execute(JobAction.UPDATE, host, "vim")
    assert first.snapshot is not None
    assert first.snapshot.updates == 11
    await executor.async_execute(JobAction.UPDATE, host, package_names=("curl",))
    checked = await executor.async_execute(JobAction.CHECK_UPDATES, host)
    assert checked.snapshot is not None
    assert checked.snapshot.updates == 10
    assert not {"vim", "curl"} & {p.name for p in checked.snapshot.packages}
    await executor.async_execute(JobAction.REBOOT, host)
    checked = await executor.async_execute(JobAction.CHECK_UPDATES, host)
    assert checked.reboot_required is False


@pytest.mark.parametrize("provider", ["dnf", "zypper"])
async def test_preview_rpm_scopes_remain_synthetic_and_keep_unknown_security(provider):
    from backend.tests.test_automation import _host

    host = _host().model_copy(update={"package_provider": provider, "packages": ()})
    executor = PreviewExecutor()
    checked = await executor.async_execute(JobAction.CHECK_UPDATES, host)
    assert checked.snapshot.updates == 2
    assert checked.snapshot.security_updates is None
    assert checked.snapshot.package_scopes == ("full", "selected", "single")
    updated = await executor.async_execute(JobAction.UPDATE, host, "curl.x86_64")
    assert updated.snapshot.updates == 1
    assert updated.snapshot.security_updates is None
    repeated = await executor.async_execute(JobAction.CHECK_UPDATES, host)
    assert repeated.snapshot.updates == 1
