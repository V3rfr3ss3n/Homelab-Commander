"""Dependency-free management UI assets packaged with the backend."""

from collections.abc import Callable, Sequence
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.params import Depends

_ASSETS = Path(__file__).with_name("frontend")
UI_HTML = (_ASSETS / "index.html").read_text(encoding="utf-8")
UI_JAVASCRIPT = (_ASSETS / "ui.js").read_text(encoding="utf-8")
UI_STYLESHEET = (_ASSETS / "ui.css").read_text(encoding="utf-8")

GROUP_JAVASCRIPT = (_ASSETS / "groups.js").read_text(encoding="utf-8")

LIST_JAVASCRIPT = (_ASSETS / "list-state.js").read_text(encoding="utf-8")
RESOURCE_JAVASCRIPT = (_ASSETS / "resource-view.js").read_text(encoding="utf-8")


def install_ui_assets(app: FastAPI, dependencies: Sequence[Depends]) -> None:
    """Serve a closed asset allowlist under the existing Ingress trust boundary."""
    assets = {
        "/ui.js": (UI_JAVASCRIPT, "application/javascript"),
        "/groups.js": (GROUP_JAVASCRIPT, "application/javascript"),
        "/list-state.js": (LIST_JAVASCRIPT, "application/javascript"),
        "/resource-view.js": (RESOURCE_JAVASCRIPT, "application/javascript"),
        "/ui.css": (UI_STYLESHEET, "text/css"),
    }
    for path, (content, media_type) in assets.items():
        app.add_api_route(
            path,
            _asset_response(content, media_type),
            methods=["GET"],
            include_in_schema=False,
            dependencies=dependencies,
        )


def _asset_response(content: str, media_type: str) -> Callable[[], Response]:
    def respond() -> Response:
        return Response(content, media_type=media_type)

    return respond
