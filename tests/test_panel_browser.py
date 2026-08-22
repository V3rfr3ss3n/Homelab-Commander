"""Real-browser regression for the Home Assistant custom panel asset."""

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
ENTRY_ID = "synthetic-entry"
JOB_ID = "00000000-0000-4000-8000-000000000002"
MANAGEMENT_URL = "https://backend.example.invalid"


def _snapshot() -> dict[str, object]:
    success = {
        "job_id": JOB_ID,
        "host_id": "00000000-0000-4000-8000-000000000001",
        "host_name": "Node 01",
        "type": "check_updates",
        "state": "success",
        "created_at": "2026-01-15T12:00:00+00:00",
        "started_at": "2026-01-15T12:00:01+00:00",
        "finished_at": "2026-01-15T12:00:03+00:00",
        "duration": 2.0,
        "exit_code": 0,
        "error_code": None,
        "short_error": None,
        "log_available": True,
    }
    failure = {
        **success,
        "job_id": "00000000-0000-4000-8000-000000000003",
        "state": "failed",
        "finished_at": "2026-01-15T11:00:03+00:00",
        "exit_code": 2,
        "error_code": "synthetic_failure",
        "short_error": "Synthetic failure",
    }
    return {
        "backend_online": True,
        "checking": False,
        "running_jobs": 0,
        "queued_jobs": 0,
        "last_job": success,
        "last_failed_job": failure,
        "hosts": [
            {
                "host_id": "00000000-0000-4000-8000-000000000001",
                "name": "Node 01",
                "distribution": "Example Linux 1.0",
                "updates": 3,
                "security_updates": 1,
                "reboot_required": False,
                "status": "ok",
                "checked_at": "2026-01-15T12:00:00+00:00",
            }
        ],
        "jobs": [success, failure],
    }


def _panel_harness() -> Starlette:
    snapshot = json.dumps(_snapshot())
    html = f"""<!doctype html>
<html><body>
<script type="module">
  import "/panel.js";
  await customElements.whenDefined("homelab-updates-panel");
  window.wsCalls = [];
  const panel = document.createElement("homelab-updates-panel");
  document.body.append(panel);
  panel.panel = {{config: {{
    entry_id: "{ENTRY_ID}",
    management_url: "{MANAGEMENT_URL}",
  }}}};
  panel.hass = {{
    language: "de",
    connection: {{
      subscribeMessage: async (callback, message) => {{
        window.wsCalls.push(message);
        callback({snapshot});
        return () => {{}};
      }},
    }},
    callWS: async (message) => {{
      window.wsCalls.push(message);
      if (message.type === "homelab_updates/job_log") {{
        return {{output: "Synthetic <redacted> & safe output", truncated: false}};
      }}
      return {{job_id: "{JOB_ID}"}};
    }},
  }};
</script>
</body></html>"""

    def index(_request: Request) -> HTMLResponse:
        return HTMLResponse(html)

    def panel_source(_request: Request) -> Response:
        return Response(PANEL_SOURCE.read_text(), media_type="text/javascript")

    return Starlette(routes=[Route("/", index), Route("/panel.js", panel_source)])


@pytest.mark.asyncio
async def test_panel_renders_main_view_and_loads_logs_on_demand(
    socket_enabled: None,
) -> None:
    """The shipped web component renders safe state and invokes only HA commands."""
    async with _live_server(_panel_harness()) as base_url, async_playwright() as api:
        browser = await api.chromium.launch(headless=True)
        page = await browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.goto(base_url)
        panel = page.locator("homelab-updates-panel")
        await panel.get_by_role("heading", name="Homelab Updates").wait_for()
        text = await panel.locator(".page").inner_text()
        assert "Online" in text
        assert "Hosts\n1" in text
        assert "Letzter Job" in text
        assert "check_updates · success" in text
        assert "synthetic_failure" in text
        manage = panel.get_by_role("link", name="Backend verwalten")
        assert await manage.get_attribute("href") == MANAGEMENT_URL

        await panel.get_by_role("button", name="Log öffnen").first.click()
        log = panel.locator("pre")
        await log.wait_for()
        assert await log.inner_text() == "Synthetic <redacted> & safe output"

        await panel.get_by_role("button", name="Hosts prüfen").click()
        calls = await page.evaluate("window.wsCalls")
        assert [call["type"] for call in calls] == [
            "homelab_updates/subscribe_panel",
            "homelab_updates/job_log",
            "homelab_updates/check_hosts",
        ]
        assert await page.evaluate("localStorage.length") == 0
        assert await page.evaluate("sessionStorage.length") == 0
        assert "synthetic-test-token" not in await page.content()
        assert errors == []
        await browser.close()
