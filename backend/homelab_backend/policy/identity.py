"""HTTP identity adapter; tokens remain transient and never enter job metadata."""

from typing import Protocol

from starlette.types import ASGIApp, Receive, Scope, Send

from .application import principal_scope
from .domain import ANONYMOUS, Principal


class PrincipalResolver(Protocol):
    async def async_authenticate(self, token: str) -> Principal | None:
        """Trusted server adapter; never infer roles from request headers/body."""


class PolicyIdentityMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        with principal_scope(ANONYMOUS):
            await self.app(scope, receive, send)
