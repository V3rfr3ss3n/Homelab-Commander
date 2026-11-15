"""Failures provide actionable references without raw exceptions or payloads."""

import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from backend.homelab_backend.app import create_app
from backend.homelab_backend.config import Settings
from backend.homelab_backend.errors import DiagnosticMiddleware
from backend.tests.test_backend_api import TOKEN, FakeExecutor, _csrf


def test_unexpected_api_error_is_safe_and_correlated(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    app = create_app(
        Settings(data_dir=tmp_path, api_token=TOKEN), executor=FakeExecutor()
    )

    @app.get("/synthetic-failure")
    def synthetic_failure() -> None:
        raise RuntimeError("private-exception-text synthetic-password")

    with TestClient(app) as client:
        with caplog.at_level(logging.ERROR):
            response = client.get(
                "/synthetic-failure", headers={"X-Request-ID": "untrusted-reference"}
            )
        assert response.status_code == 500
        data = response.json()
        assert data["error_code"] == "internal_error"
        assert data["operation"] == "synthetic_failure"
        assert len(data["request_id"]) == 32
        assert response.headers["X-Request-ID"] == data["request_id"]
        assert response.headers["Cache-Control"] == "no-store"
        assert datetime.fromisoformat(data["timestamp"]).tzinfo is not None
        assert data["request_id"] in caplog.text
        assert "test_error_diagnostics.py:" in caplog.text
        for secret in (
            "private-exception-text",
            "synthetic-password",
            "untrusted-reference",
        ):
            assert secret not in response.text + caplog.text
        assert client.get("/info").status_code == 404
        assert (
            client.get(
                "/api/v1/info", headers={"Authorization": f"Bearer {TOKEN}"}
            ).status_code
            == 200
        )


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422, 429, 503])
def test_http_errors_preserve_status_detail_and_headers(
    tmp_path: Path, status: int
) -> None:
    app = create_app(
        Settings(data_dir=tmp_path, api_token=TOKEN), executor=FakeExecutor()
    )

    @app.get("/synthetic-http-error")
    def synthetic_http_error() -> None:
        raise HTTPException(status, "Safe explanation", headers={"Retry-After": "5"})

    with TestClient(app) as client:
        response = client.get("/synthetic-http-error")
    assert response.status_code == status
    assert response.json()["detail"] == "Safe explanation"
    assert response.json()["error_code"] == f"http_{status}"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert response.headers["Retry-After"] == "5"


def test_validation_does_not_echo_input_or_context(tmp_path: Path) -> None:
    app = create_app(
        Settings(data_dir=tmp_path, api_token=TOKEN), executor=FakeExecutor()
    )
    with TestClient(app) as client:
        response = client.post(
            "/ui-api/auth/login",
            headers={"X-CSRF-Token": _csrf(client)},
            json={"api_token": {"secret": "synthetic-secret"}},
        )
        assert response.status_code == 422
        assert response.json()["error_code"] == "validation_error"
        assert "synthetic-secret" not in response.text
        assert "input" not in response.json()["detail"][0]
        assert "ctx" not in response.json()["detail"][0]
        response = client.post(
            "/ui-api/auth/login",
            headers={"X-CSRF-Token": _csrf(client)},
            json={
                "api_token": TOKEN,
                "synthetic-private-field": "synthetic-private-value",
            },
        )
        assert response.status_code == 422
        assert "synthetic-private" not in response.text


async def test_middleware_non_http_and_interrupted_response(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sent: list[Message] = []

    send = AsyncMock(side_effect=sent.append)
    receive = AsyncMock(return_value={"type": "http.request"})

    async def application(scope: Scope, _receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await send({"type": "lifespan.startup.complete"})
            return
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise RuntimeError("synthetic-secret")

    middleware = DiagnosticMiddleware(application)
    await middleware({"type": "lifespan"}, receive, send)
    assert sent == [{"type": "lifespan.startup.complete"}]
    with pytest.raises(RuntimeError, match="Response interrupted"):
        await middleware({"type": "http"}, receive, send)
    assert "synthetic-secret" not in caplog.text
