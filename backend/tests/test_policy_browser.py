"""Policy denial is visible without expiring a valid standalone/Ingress session."""

import json
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect

from backend.homelab_backend.app import create_app
from backend.homelab_backend.config import Settings
from backend.homelab_backend.policy.domain import (
    Decision,
    Permission,
    PolicyEngine,
    PrincipalKind,
)
from backend.tests.test_backend_api import TOKEN, FakeExecutor
from backend.tests.test_ui_browser import (
    _live_server,
    _PrefixProxy,
    _wait_for_connection,
)


@pytest.mark.parametrize("ingress", [True, False])
async def test_policy_denial_keeps_session_and_safe_diagnostics(
    tmp_path: Path, socket_enabled: None, monkeypatch: pytest.MonkeyPatch, ingress: bool
) -> None:
    original = PolicyEngine.decide

    def deny_write(self, principal, permission, target=None, operation=None):
        if (
            permission is Permission.HOST_WRITE
            and principal.kind is PrincipalKind.HUMAN
        ):
            return Decision(False, "policy_denied")
        return original(self, principal, permission, target, operation)

    monkeypatch.setattr(PolicyEngine, "decide", deny_write)
    settings = Settings(data_dir=tmp_path, api_token=TOKEN, ingress_mode=ingress)
    app = create_app(
        settings,
        executor=FakeExecutor(),
        ingress_proxy_addresses=frozenset({"supervisor-proxy"}) if ingress else None,
    )
    prefix = "/nested/policy" if ingress else ""
    async with (
        _live_server(_PrefixProxy(app, prefix) if ingress else app) as base,
        async_playwright() as api,
    ):
        browser = await api.chromium.launch()
        context = await browser.new_context()
        await context.grant_permissions(
            ["clipboard-read", "clipboard-write"], origin=base
        )
        page = await context.new_page()
        await page.goto(base + prefix + "/")
        if not ingress:
            await page.locator("#token").fill(TOKEN)
            await page.locator("#connect").click()
        await _wait_for_connection(page)
        await page.evaluate("""async()=>{
            await window.operatorUI.run(null,()=>window.operatorUI.request("hosts",{
                method:"POST",body:{name:"Synthetic",address:"private-marker.example.invalid",username:"automation"}
            }));
        }""")
        await expect(page.locator("#message-text")).to_contain_text("backend policy")
        await expect(page.locator("#connection-label")).to_have_text("Connected")
        await expect(page.locator("#protected-content")).to_be_visible()
        await page.locator("#error-details summary").click()
        await page.locator("#copy-error-diagnostic").click()
        diagnostic = json.loads(await page.evaluate("navigator.clipboard.readText()"))
        assert diagnostic["error_code"] == "policy_denied"
        assert diagnostic["http_status"] == 403
        assert len(diagnostic["request_id"]) == 32
        assert "private-marker" not in json.dumps(diagnostic)
        assert TOKEN not in json.dumps(diagnostic)
        await page.locator("#refresh").click()
        await expect(page.locator("#connection-label")).to_have_text("Connected")
        await browser.close()
