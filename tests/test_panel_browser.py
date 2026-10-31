"""Real-browser regression for direct Home Assistant sidebar navigation."""

import json
from pathlib import Path

import pytest
from playwright.async_api import async_playwright
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.routing import Route

from backend.tests.test_ui_browser import _live_server

PANEL_SOURCE = (
    Path(__file__).parents[1] / "custom_components/homelab_updates/frontend/panel.js"
)
MANAGEMENT_URL = "https://backend.example.invalid"
APP_ROUTE = "/app/synthetic_repository_homelab_updates"


def _panel_harness(management_url: str) -> Starlette:
    config = json.dumps({"management_url": management_url})
    html = f"""<!doctype html>
<html><body>
<script type="module">
  import "/panel.js";
  await customElements.whenDefined("homelab-updates-panel");
  const panel = document.createElement("homelab-updates-panel");
  document.body.append(panel);
  panel.panel = {{config: {config}}};
  panel.hass = {{
    connection: {{subscribeMessage: () => {{throw Error("Unexpected subscription");}}}},
    callWS: () => {{throw Error("Unexpected action");}},
  }};
</script>
</body></html>"""

    def index(_request: Request) -> HTMLResponse:
        return HTMLResponse(html)

    def panel_source(_request: Request) -> Response:
        return Response(PANEL_SOURCE.read_text(), media_type="text/javascript")

    def previous(_request: Request) -> HTMLResponse:
        return HTMLResponse('<a href="/">Homelab Commander</a>')

    return Starlette(
        routes=[
            Route("/", index),
            Route("/previous", previous),
            Route("/panel.js", panel_source),
        ]
    )


@pytest.mark.parametrize("destination", [APP_ROUTE, MANAGEMENT_URL])
async def test_sidebar_opens_backend_directly_in_current_tab(
    socket_enabled: None, destination: str
) -> None:
    """Open the backend without a summary, action, token or extra browser tab."""
    async with (
        _live_server(_panel_harness(destination)) as base_url,
        async_playwright() as api,
    ):
        browser = await api.chromium.launch(headless=True)
        page = await browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        target = base_url + destination if destination.startswith("/") else destination
        await page.route(
            target,
            lambda route: route.fulfill(
                content_type="text/html", body="<h1>Synthetic backend UI</h1>"
            ),
        )
        await page.goto(base_url + "/previous")
        await page.get_by_role("link", name="Homelab Commander").click()
        await page.wait_for_url(target)
        await page.get_by_role("heading", name="Synthetic backend UI").wait_for()
        assert len(page.context.pages) == 1
        assert await page.evaluate("localStorage.length") == 0
        assert await page.evaluate("sessionStorage.length") == 0
        assert errors == []
        await page.go_back()
        await page.wait_for_url(base_url + "/previous")
        await browser.close()


@pytest.mark.parametrize(
    "destination",
    [
        "",
        "javascript:alert(1)",
        "//other.invalid/app/x",
        "https://[",
        "https://user:pass@backend.example.invalid",
    ],
)
async def test_sidebar_rejects_unsafe_navigation(
    socket_enabled: None, destination: str
) -> None:
    """Missing or unsupported destinations cannot execute script or navigate."""
    async with (
        _live_server(_panel_harness(destination)) as base_url,
        async_playwright() as api,
    ):
        browser = await api.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(base_url)
        await page.wait_for_function(
            'document.querySelector("homelab-updates-panel") !== null'
        )
        assert page.url == base_url + "/"
        await browser.close()
