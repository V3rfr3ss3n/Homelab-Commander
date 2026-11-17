"""Allowlisted failure diagnostics without exception messages or request data."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .failure_logging import log_internal_failure
from .policy.application import AuthorizationDenied
from .version import __version__


def _diagnostics(scope: Scope, code: str) -> dict[str, str]:
    route = scope.get("route")
    return {
        "error_code": code,
        "request_id": scope["hlc_request_id"],
        "timestamp": datetime.now(UTC).isoformat(),
        "component": "backend",
        "operation": getattr(route, "name", "request"),
        "version": __version__,
    }


class DiagnosticMiddleware:
    """Catch failures before ASGI server logging can expose raw exceptions."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        scope["hlc_request_id"] = uuid4().hex
        started = False

        async def send_response(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                message.setdefault("headers", []).append((
                    b"x-request-id",
                    scope["hlc_request_id"].encode("ascii"),
                ))
            await send(message)

        try:
            await self.app(scope, receive, send_response)
        except Exception as error:
            diagnostic = _diagnostics(scope, "internal_error")
            log_internal_failure(
                error, diagnostic["request_id"], diagnostic["operation"]
            )
            if started:
                # Current API responses are buffered; protect any future streaming
                # path from propagating sensitive exception details to the server.
                raise RuntimeError(
                    "Response interrupted; see safe failure reference"
                ) from None
            await JSONResponse(
                {
                    "detail": (
                        "An internal error occurred. Retry read-only requests "
                        "or inspect the job before repeating an action."
                    ),
                    **diagnostic,
                },
                status_code=500,
                headers={"Cache-Control": "no-store"},
            )(scope, receive, send_response)


def install_error_handlers(app: FastAPI) -> None:
    """Add compatible diagnostics to expected HTTP and validation failures."""
    app.add_middleware(DiagnosticMiddleware)

    @app.exception_handler(AuthorizationDenied)
    def authorization_error(
        request: Request, error: AuthorizationDenied
    ) -> JSONResponse:
        return JSONResponse(
            {"detail": str(error), **_diagnostics(request.scope, "policy_denied")},
            status_code=403,
            headers={"Cache-Control": "no-store"},
        )

    @app.exception_handler(HTTPException)
    def http_error(request: Request, error: HTTPException) -> JSONResponse:
        return JSONResponse(
            {
                "detail": error.detail,
                **_diagnostics(request.scope, f"http_{error.status_code}"),
            },
            status_code=error.status_code,
            headers={**(error.headers or {}), "Cache-Control": "no-store"},
        )

    @app.exception_handler(RequestValidationError)
    def validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        # Pydantic's default body includes input and context, potentially tokens.
        # Extra-field names may themselves contain data supplied by the caller.
        fields = {"body", "query", "path", "header", "cookie"}
        for definition in (
            app.openapi().get("components", {}).get("schemas", {}).values()
        ):
            fields.update(definition.get("properties", {}))
        for path in app.openapi().get("paths", {}).values():
            for operation in path.values():
                if isinstance(operation, dict):
                    fields.update(
                        item["name"] for item in operation.get("parameters", [])
                    )
        details = [
            {
                "loc": [
                    part if isinstance(part, int) or part in fields else "field"
                    for part in item["loc"]
                ],
                "type": item["type"],
                "msg": "Invalid request value",
            }
            for item in error.errors()
        ]
        return JSONResponse(
            {"detail": details, **_diagnostics(request.scope, "validation_error")},
            status_code=422,
            headers={"Cache-Control": "no-store"},
        )
