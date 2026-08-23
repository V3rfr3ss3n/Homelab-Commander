"""Real-browser regression tests for the dependency-free management UI."""

import asyncio
import json
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from playwright.async_api import Dialog, Page, Route, async_playwright

from backend.homelab_backend.app import create_app
from backend.homelab_backend.config import Settings
from backend.homelab_backend.ui_sessions import UiSessionStore
from backend.tests.test_backend_api import TOKEN, FakeExecutor

JOB_ID_CHECK = "00000000-0000-4000-8000-000000000091"
JOB_ID_CONNECTION = "00000000-0000-4000-8000-000000000092"
JOB_ID_FAILURE = "00000000-0000-4000-8000-000000000093"


class _BrowserClock:
    """Monotonic clock controlled by a browser test."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@asynccontextmanager
async def _live_server(app: Any) -> AsyncIterator[str]:
    """Serve one ASGI app on an ephemeral loopback port."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(app, log_level="critical", lifespan="on", access_log=False)
    )
    task = asyncio.create_task(server.serve(sockets=[listener]))
    for _attempt in range(1_000):
        if server.started:
            break
        if task.done():
            await task
        await asyncio.sleep(0)
    else:
        server.should_exit = True
        await task
        raise AssertionError("Synthetic UI server did not start")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await task


class _PrefixProxy:
    """Small Supervisor-Ingress-style path-prefix proxy for browser tests."""

    def __init__(self, app: Any, prefix: str) -> None:
        self._app = app
        self._prefix = prefix
        self.forwarded_paths: list[str] = []

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "lifespan":
            await self._app(scope, receive, send)
            return
        path = scope["path"]
        if path != self._prefix and not path.startswith(f"{self._prefix}/"):
            await self._not_found(scope, receive, send)
            return
        forwarded = dict(scope)
        forwarded["root_path"] = f"{scope.get('root_path', '')}{self._prefix}"
        forwarded["path"] = path.removeprefix(self._prefix) or "/"
        forwarded["raw_path"] = forwarded["path"].encode()
        forwarded["client"] = ("supervisor-proxy", 12345)
        self.forwarded_paths.append(forwarded["path"])
        await self._app(forwarded, receive, send)

    @staticmethod
    async def _not_found(_scope: dict[str, Any], _receive: Any, send: Any) -> None:
        await send({
            "type": "http.response.start",
            "status": 404,
            "headers": [(b"content-type", b"text/plain")],
        })
        await send({"type": "http.response.body", "body": b"not found"})


async def _wait_for_message(page: Page, text: str) -> None:
    await page.locator("#message").filter(has_text=text).wait_for()


async def _accept_dialog(dialog: Dialog) -> None:
    await dialog.accept()


async def _connect_standalone(page: Page, base_url: str) -> None:
    await page.goto(f"{base_url}/")
    await page.locator("#token").fill(TOKEN)
    await page.locator("#connect").click()
    await _wait_for_message(page, "Connected")


async def _reject_authentication(route: Route) -> None:
    await route.fulfill(
        status=401,
        content_type="application/json",
        body='{"detail":"Authentication expired"}',
    )


async def _reject_ingress_authorization(route: Route) -> None:
    await route.fulfill(
        status=403,
        content_type="application/json",
        body='{"detail":"Ingress authorization expired"}',
    )


@pytest.mark.asyncio
async def test_standalone_ui_buttons_work_and_errors_are_visible(
    tmp_path: Path,
    socket_enabled: None,
) -> None:
    """A browser can authenticate, read, copy, create, and see auth failures."""
    app = create_app(
        Settings(data_dir=tmp_path, api_token=TOKEN), executor=FakeExecutor()
    )
    async with _live_server(app) as base_url, async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        await context.grant_permissions(
            ["clipboard-read", "clipboard-write"], origin=base_url
        )
        page = await context.new_page()
        errors: list[str] = []
        request_paths: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: request_paths.append(request.url))

        await page.goto(f"{base_url}/")
        assert await page.locator("#connection-label").inner_text() == "Not connected"
        assert (
            await page.locator("#connection-hint").inner_text()
            == "Enter your API token to load backend data."
        )
        assert await page.locator("#connect-placeholder").is_visible()
        assert await page.locator("#protected-content").is_hidden()
        assert await page.locator("#dashboard").inner_text() == ""
        assert "Hosts\n0" not in await page.locator("body").inner_text()

        await page.locator("#token").fill(TOKEN)
        await page.locator("#connect").click()
        await _wait_for_message(page, "Connected")
        assert await page.locator("#connection-label").inner_text() == "Connected"
        assert await page.locator("#protected-content").is_visible()
        public_key = await page.locator("#key").inner_text()
        assert public_key.startswith("ssh-ed25519 ")
        assert await page.locator("#token").input_value() == ""

        expected_paths = {
            "/ui-api/auth/login",
            "/ui-api/info",
            "/ui-api/hosts",
            "/ui-api/public-key",
            "/ui-api/custom-tasks",
            "/ui-api/jobs",
        }
        assert expected_paths <= {url.removeprefix(base_url) for url in request_paths}
        assert all(TOKEN not in url for url in request_paths)

        await page.locator("#copy-key").click()
        await _wait_for_message(page, "Copied")
        copied = await page.evaluate("navigator.clipboard.readText()")
        assert copied == public_key

        await page.locator("#host-name").fill("Node 01")
        await page.locator("#host-address").fill("node-01.example.invalid")
        await page.locator("#host-user").fill("automation")
        await page.locator("#host-form button[type=submit]").click()
        await _wait_for_message(page, "Host added")
        assert await page.locator("#hosts").get_by_text("Node 01").is_visible()
        assert await page.locator('[data-action="update"]').is_visible()
        assert await page.locator('[data-action="reboot"]').is_visible()

        await page.locator("#task-name").fill("Read uptime")
        await page.locator("#task-argv").fill('["uptime"]')
        await page.locator("#task-form button[type=submit]").click()
        await _wait_for_message(page, "Task added")
        assert await page.locator("#tasks").get_by_text("Read uptime").is_visible()

        await page.locator('[data-action="test_connection"]').click()
        await _wait_for_message(page, "test connection queued")
        await page.locator('[data-action="check_updates"]').click()
        await _wait_for_message(page, "check updates queued")
        page.on("dialog", _accept_dialog)
        await page.locator("#tasks button[data-task][data-host]").click()
        await _wait_for_message(page, "Task queued")
        relative_requests = {url.removeprefix(base_url) for url in request_paths}
        assert any("/actions/test_connection" in path for path in relative_requests)
        assert any("/actions/check_updates" in path for path in relative_requests)
        assert any("/tasks/" in path for path in relative_requests)

        async def failed_jobs(route: Route) -> None:
            await route.fulfill(
                status=200,
                content_type="application/json",
                body=(
                    '[{"id":"00000000-0000-4000-8000-000000000099",'
                    '"action":"check_updates",'
                    '"created_at":"2026-01-15T12:00:00Z",'
                    '"state":"failed",'
                    '"error_code":"check_updates_apt_cache_refresh_failed"}]'
                ),
            )

        await page.route("**/ui-api/jobs", failed_jobs, times=1)
        await page.locator("#connect").click()
        await _wait_for_message(page, "Connected")
        assert (
            await page
            .locator("#jobs")
            .get_by_text("Check updates failed during APT cache refresh")
            .is_visible()
        )

        await page.route("**/ui-api/info", _reject_authentication, times=1)
        await page.locator("#connect").click()
        await _wait_for_message(page, "Authentication expired")
        assert await page.locator("#connection-label").inner_text() == "Not connected"
        assert await page.locator("#protected-content").is_hidden()
        assert await page.locator("#hosts").inner_text() == ""

        await page.locator("#token").fill(TOKEN)
        await page.locator("#connect").click()
        await _wait_for_message(page, "Connected")
        assert await page.locator("#hosts").get_by_text("Node 01").is_visible()

        await page.reload()
        await _wait_for_message(page, "Connected")
        assert await page.locator("#connection-label").inner_text() == "Connected"
        assert await page.locator("#connect-placeholder").is_hidden()
        assert await page.locator("#protected-content").is_visible()
        assert await page.locator("#token").input_value() == ""
        assert "Hosts\n1" in await page.locator("#dashboard").inner_text()
        assert await page.locator("#hosts").get_by_text("Node 01").is_visible()
        assert (await page.locator("#key").inner_text()).startswith("ssh-ed25519 ")
        assert await page.locator("#jobs").inner_text() != ""

        cookies = await context.cookies()
        session_cookie = next(
            cookie for cookie in cookies if cookie["name"] == "hul_ui_session"
        )
        assert session_cookie["httpOnly"] is True
        assert session_cookie["sameSite"] == "Strict"
        assert session_cookie["secure"] is False
        assert session_cookie["value"] != TOKEN
        assert TOKEN not in await page.evaluate("document.documentElement.outerHTML")
        assert TOKEN not in await page.evaluate("document.cookie")
        assert await page.evaluate("localStorage.length") == 0
        assert await page.evaluate("sessionStorage.length") == 0

        await page.locator("#disconnect").click()
        await _wait_for_message(page, "Disconnected")
        assert await page.locator("#connection-label").inner_text() == "Not connected"
        assert await page.locator("#protected-content").is_hidden()
        assert await page.locator("#token").input_value() == ""
        assert await page.locator("#hosts").inner_text() == ""

        await page.reload()
        assert await page.locator("#connection-label").inner_text() == "Not connected"
        assert await page.locator("#protected-content").is_hidden()

        await page.locator("#token").fill("wrong-token-that-is-still-at-least-32-chars")
        await page.locator("#connect").click()
        await _wait_for_message(page, "Authentication failed")
        assert await page.locator("#connection-label").inner_text() == "Not connected"
        assert errors == []
        await browser.close()


@pytest.mark.asyncio
async def test_ingress_ui_keeps_assets_and_api_calls_under_prefix(
    tmp_path: Path,
    socket_enabled: None,
) -> None:
    """Relative URLs and CSRF work behind a synthetic Supervisor path prefix."""
    prefix = "/ingress/synthetic-instance"
    app = create_app(
        Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=True),
        executor=FakeExecutor(),
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}),
    )
    proxy = _PrefixProxy(app, prefix)
    async with (
        _live_server(proxy) as base_url,
        async_playwright() as playwright,
    ):
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        errors: list[str] = []
        request_paths: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: request_paths.append(request.url))

        await page.goto(f"{base_url}{prefix}/")
        await _wait_for_message(page, "Connected")
        assert proxy.forwarded_paths[0] == "/"
        assert "//" not in proxy.forwarded_paths
        assert await page.locator("#token-field").is_hidden()
        assert await page.locator("#disconnect").is_hidden()
        assert (await page.locator("#key").inner_text()).startswith("ssh-ed25519 ")

        await page.locator("#host-name").fill("Node 01")
        await page.locator("#host-address").fill("node-01.example.invalid")
        await page.locator("#host-user").fill("automation")
        await page.locator("#host-form button[type=submit]").click()
        await _wait_for_message(page, "Host added")
        assert await page.locator("#hosts").get_by_text("Node 01").is_visible()
        await page.locator('[data-action="test_connection"]').click()
        await _wait_for_message(page, "test connection queued")
        await page.locator("#jobs").get_by_text("success", exact=True).wait_for()
        await page.locator("#jobs button[data-job-log]").first.click()
        await page.locator("#job-detail").wait_for(state="visible")
        assert "Node 01" in await page.locator("#job-metadata").inner_text()
        assert "test_connection" in await page.locator("#job-metadata").inner_text()
        assert f"{base_url}{prefix}/#/jobs/" in page.url

        relevant = [url.removeprefix(base_url) for url in request_paths]
        assert f"{prefix}/ui.js" in relevant
        assert f"{prefix}/ui.css" in relevant
        assert f"{prefix}/ui-api/info" in relevant
        assert f"{prefix}/ui-api/hosts" in relevant
        assert any(
            path.startswith(f"{prefix}/ui-api/hosts/")
            and path.endswith("/actions/test_connection")
            for path in relevant
        )
        assert all(path.startswith(prefix) for path in relevant)

        await page.route("**/ui-api/info", _reject_ingress_authorization, times=1)
        await page.locator("#connect").click()
        await _wait_for_message(page, "Ingress authorization expired")
        assert await page.locator("#connection-label").inner_text() == "Not connected"
        assert await page.locator("#protected-content").is_hidden()
        assert await page.locator("#hosts").inner_text() == ""
        assert errors == []
        await browser.close()


@pytest.mark.asyncio
async def test_standalone_job_deep_link_requires_session_and_survives_reload(
    tmp_path: Path,
    socket_enabled: None,
) -> None:
    """A hash deep link waits for login, returns to the job, and contains no token."""
    app = create_app(
        Settings(data_dir=tmp_path, api_token=TOKEN), executor=FakeExecutor()
    )
    async with _live_server(app) as base_url, async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        setup_page = await browser.new_page()
        await _connect_standalone(setup_page, base_url)
        await setup_page.locator("#host-name").fill("Node 01")
        await setup_page.locator("#host-address").fill("node-01.example.invalid")
        await setup_page.locator("#host-user").fill("automation")
        await setup_page.locator("#host-form button[type=submit]").click()
        await _wait_for_message(setup_page, "Host added")
        await setup_page.locator('[data-action="test_connection"]').click()
        await _wait_for_message(setup_page, "test connection queued")
        await setup_page.locator("#jobs").get_by_text("success", exact=True).wait_for()
        job_id = await setup_page.locator(
            "#jobs button[data-job-log]"
        ).first.get_attribute("data-job-log")
        assert job_id is not None
        await setup_page.locator("#disconnect").click()
        await _wait_for_message(setup_page, "Disconnected")
        await setup_page.close()

        page = await browser.new_page()
        request_urls: list[str] = []
        page.on("request", lambda request: request_urls.append(request.url))
        deep_link = f"{base_url}/#/jobs/{job_id}"
        await page.goto(deep_link)
        assert await page.locator("#connection-label").inner_text() == "Not connected"
        assert await page.locator("#protected-content").is_hidden()
        assert not any(f"/ui-api/jobs/{job_id}" in url for url in request_urls)

        await page.locator("#token").fill(TOKEN)
        await page.locator("#connect").click()
        await _wait_for_message(page, "Connected")
        assert await page.locator("#job-detail").is_visible()
        metadata = await page.locator("#job-metadata").inner_text()
        assert job_id in metadata
        assert "Node 01" in metadata
        assert "test_connection" in metadata
        assert "success" in metadata
        assert (
            "checked [redacted] as [redacted]"
            in await page.locator("#log").inner_text()
        )
        assert all(TOKEN not in url for url in request_urls)

        await page.reload()
        await _wait_for_message(page, "Connected")
        assert page.url == deep_link
        assert await page.locator("#job-detail").is_visible()
        assert job_id in await page.locator("#job-metadata").inner_text()

        await page.locator("#disconnect").click()
        await _wait_for_message(page, "Disconnected")
        assert await page.locator("#job-detail").is_hidden()
        assert await page.locator("#protected-content").is_hidden()
        assert TOKEN not in page.url
        await browser.close()


@pytest.mark.asyncio
async def test_job_polling_tracks_terminal_states_and_refreshes_hosts(
    tmp_path: Path,
    socket_enabled: None,
) -> None:
    """Queued jobs advance without Refresh and update host/dashboard state."""
    app = create_app(
        Settings(data_dir=tmp_path, api_token=TOKEN), executor=FakeExecutor()
    )
    async with _live_server(app) as base_url, async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await _connect_standalone(page, base_url)

        await page.locator("#host-name").fill("Node 01")
        await page.locator("#host-address").fill("node-01.example.invalid")
        await page.locator("#host-user").fill("automation")
        await page.locator("#host-form button[type=submit]").click()
        await _wait_for_message(page, "Host added")
        host_id = await page.locator('[data-action="check_updates"]').get_attribute(
            "data-host"
        )
        assert host_id is not None

        scenario: dict[str, object] = {
            "action": "check_updates",
            "job_id": JOB_ID_CHECK,
            "states": ["queued", "running", "success"],
            "calls": 0,
            "connection_runs": 0,
            "in_flight": 0,
            "max_in_flight": 0,
        }

        def job_payload(current: str | None = None) -> dict[str, object]:
            if current is None:
                states = scenario["states"]
                assert isinstance(states, list)
                calls = int(scenario["calls"])
                current = str(states[min(calls, len(states) - 1)])
                scenario["calls"] = calls + 1
            return {
                "id": scenario["job_id"],
                "action": scenario["action"],
                "host_id": host_id,
                "custom_task_id": None,
                "state": current,
                "created_at": "2026-01-15T12:00:00Z",
                "started_at": None,
                "finished_at": None,
                "error_code": "sudo_unavailable" if current == "failed" else None,
                "reboot_required": False,
            }

        async def jobs(route: Route) -> None:
            scenario["in_flight"] = int(scenario["in_flight"]) + 1
            scenario["max_in_flight"] = max(
                int(scenario["max_in_flight"]), int(scenario["in_flight"])
            )
            await asyncio.sleep(0.05)
            payload = job_payload()
            scenario["in_flight"] = int(scenario["in_flight"]) - 1
            await route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps([payload]),
            )

        async def hosts(route: Route) -> None:
            checked = (
                scenario["action"] == "check_updates" and int(scenario["calls"]) >= 2
            )
            payload = [
                {
                    "id": host_id,
                    "name": "Node 01",
                    "address": "node-01.example.invalid",
                    "port": 22,
                    "username": "automation",
                    "package_provider": "debian_apt",
                    "distribution": "Example Linux" if checked else None,
                    "distribution_version": "2.0" if checked else None,
                    "kernel": "2.0.0-example" if checked else None,
                    "updates": 7 if checked else 0,
                    "security_updates": 2 if checked else 0,
                    "reboot_required": checked,
                    "status": "ok" if checked else None,
                    "checked_at": "2026-01-15T12:00:00Z" if checked else None,
                    "created_at": "2026-01-15T11:00:00Z",
                    "updated_at": "2026-01-15T12:00:00Z",
                }
            ]
            await route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(payload),
            )

        async def check_action(route: Route) -> None:
            scenario.update({
                "action": "check_updates",
                "job_id": JOB_ID_CHECK,
                "states": ["queued", "running", "success"],
                "calls": 0,
            })
            await route.fulfill(
                status=202,
                content_type="application/json",
                body=json.dumps(job_payload("queued")),
            )

        async def connection_action(route: Route) -> None:
            run_number = int(scenario["connection_runs"])
            scenario["connection_runs"] = run_number + 1
            scenario.update({
                "action": "test_connection",
                "job_id": JOB_ID_CONNECTION if run_number == 0 else JOB_ID_FAILURE,
                "states": (
                    ["queued", "running", "success"]
                    if run_number == 0
                    else ["queued", "failed"]
                ),
                "calls": 0,
            })
            await route.fulfill(
                status=202,
                content_type="application/json",
                body=json.dumps(job_payload("queued")),
            )

        await page.route("**/ui-api/jobs", jobs)
        await page.route("**/ui-api/hosts", hosts)
        await page.route("**/ui-api/hosts/*/actions/check_updates", check_action)
        await page.route("**/ui-api/hosts/*/actions/test_connection", connection_action)

        await page.locator('[data-action="check_updates"]').click()
        await _wait_for_message(page, "check updates queued")
        await page.locator("#jobs").get_by_text("queued", exact=True).wait_for()
        assert (
            await page.locator('[data-action="check_updates"]').inner_text()
            == "Running…"
        )
        await page.locator("#jobs").get_by_text("running", exact=True).wait_for()
        await page.locator("#jobs").get_by_text("success", exact=True).wait_for()
        assert "Example Linux 2.0" in await page.locator("#hosts").inner_text()
        assert (
            "7 updates · 2 security · reboot required"
            in await page.locator("#hosts").inner_text()
        )
        assert "Running jobs\n0" in await page.locator("#dashboard").inner_text()
        assert "Queued jobs\n0" in await page.locator("#dashboard").inner_text()

        await page.locator('[data-action="test_connection"]').click()
        await _wait_for_message(page, "test connection queued")
        await page.locator("#jobs").get_by_text("running", exact=True).wait_for()
        await page.locator("#jobs").get_by_text("success", exact=True).wait_for()

        await page.locator('[data-action="test_connection"]').click()
        await _wait_for_message(page, "test connection queued")
        await (
            page
            .locator("#jobs")
            .get_by_text("Non-interactive sudo is not available", exact=True)
            .wait_for()
        )
        assert (
            "Last failed job\ntest_connection · sudo_unavailable"
            in await page.locator("#dashboard").inner_text()
        )

        calls_after_terminal = int(scenario["calls"])
        await page.wait_for_timeout(2_000)
        assert int(scenario["calls"]) == calls_after_terminal
        assert scenario["max_in_flight"] == 1
        await browser.close()


@pytest.mark.asyncio
async def test_reload_resumes_active_polling_and_disconnect_stops_it(
    tmp_path: Path,
    socket_enabled: None,
) -> None:
    """Recovered sessions resume one poller, while logout cancels its timer."""
    app = create_app(
        Settings(data_dir=tmp_path, api_token=TOKEN), executor=FakeExecutor()
    )
    async with _live_server(app) as base_url, async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await _connect_standalone(page, base_url)

        await page.locator("#host-name").fill("Node 01")
        await page.locator("#host-address").fill("node-01.example.invalid")
        await page.locator("#host-user").fill("automation")
        await page.locator("#host-form button[type=submit]").click()
        await _wait_for_message(page, "Host added")
        host_id = await page.locator('[data-action="check_updates"]').get_attribute(
            "data-host"
        )
        assert host_id is not None

        scenario: dict[str, object] = {
            "states": ["queued", "running", "success"],
            "calls": 0,
            "runs": 0,
            "job_id": JOB_ID_CHECK,
        }

        def payload(state: str) -> dict[str, object]:
            return {
                "id": scenario["job_id"],
                "action": "check_updates",
                "host_id": host_id,
                "custom_task_id": None,
                "state": state,
                "created_at": "2026-01-15T12:00:00Z",
                "started_at": None,
                "finished_at": None,
                "error_code": None,
                "reboot_required": False,
            }

        async def jobs(route: Route) -> None:
            states = scenario["states"]
            assert isinstance(states, list)
            calls = int(scenario["calls"])
            state_name = str(states[min(calls, len(states) - 1)])
            scenario["calls"] = calls + 1
            await route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps([payload(state_name)]),
            )

        async def action(route: Route) -> None:
            run_number = int(scenario["runs"])
            scenario["runs"] = run_number + 1
            scenario.update({
                "states": (
                    ["queued", "running", "success"]
                    if run_number == 0
                    else ["queued", "running"]
                ),
                "calls": 0,
                "job_id": JOB_ID_CHECK if run_number == 0 else JOB_ID_CONNECTION,
            })
            await route.fulfill(
                status=202,
                content_type="application/json",
                body=json.dumps(payload("queued")),
            )

        await page.route("**/ui-api/jobs", jobs)
        await page.route("**/ui-api/hosts/*/actions/check_updates", action)

        await page.locator('[data-action="check_updates"]').click()
        await _wait_for_message(page, "check updates queued")
        await page.locator("#jobs").get_by_text("queued", exact=True).wait_for()
        await page.reload()
        await _wait_for_message(page, "Connected")
        await page.locator("#jobs").get_by_text("success", exact=True).wait_for()

        await page.locator('[data-action="check_updates"]').click()
        await _wait_for_message(page, "check updates queued")
        await page.locator("#jobs").get_by_text("running", exact=True).wait_for()
        await page.locator("#disconnect").click()
        await _wait_for_message(page, "Disconnected")
        calls_after_disconnect = int(scenario["calls"])
        await page.wait_for_timeout(2_000)
        assert int(scenario["calls"]) == calls_after_disconnect
        assert await page.locator("#protected-content").is_hidden()
        await browser.close()


@pytest.mark.asyncio
async def test_expired_and_invalid_sessions_return_to_safe_login_state(
    tmp_path: Path,
    socket_enabled: None,
) -> None:
    """A stale cookie cannot retain protected data or trigger a refresh loop."""
    clock = _BrowserClock()
    sessions = UiSessionStore(
        clock=clock,
        token_factory=lambda: "synthetic-opaque-ui-session",
        absolute_lifetime=100,
        idle_timeout=10,
    )
    app = create_app(
        Settings(data_dir=tmp_path, api_token=TOKEN),
        executor=FakeExecutor(),
        session_store=sessions,
    )
    async with _live_server(app) as base_url, async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await _connect_standalone(page, base_url)

        clock.now = 11
        await page.locator("#connect").click()
        await (
            page
            .locator("#connection-label")
            .filter(has_text="Not connected")
            .wait_for()
        )
        assert (
            await page.locator("#connection-hint").inner_text()
            == "Session expired. Please connect again."
        )
        assert await page.locator("#protected-content").is_hidden()
        assert await page.locator("#token-field").is_visible()

        await page.reload()
        assert await page.locator("#connection-label").inner_text() == "Not connected"
        assert not any(
            cookie["name"] == "hul_ui_session" for cookie in await context.cookies()
        )

        await context.add_cookies([
            {
                "name": "hul_ui_session",
                "value": "invalid-opaque-ui-session",
                "domain": "127.0.0.1",
                "path": "/ui-api",
                "httpOnly": True,
                "sameSite": "Strict",
            }
        ])
        await page.reload()
        assert await page.locator("#connection-label").inner_text() == "Not connected"
        assert await page.locator("#protected-content").is_hidden()
        assert not any(
            cookie["name"] == "hul_ui_session" for cookie in await context.cookies()
        )
        await browser.close()
