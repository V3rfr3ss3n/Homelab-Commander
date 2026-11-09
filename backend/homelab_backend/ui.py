"""Dependency-free management UI assets packaged with the backend."""

from pathlib import Path

_ASSETS = Path(__file__).with_name("frontend")
UI_HTML = (_ASSETS / "index.html").read_text(encoding="utf-8")
UI_JAVASCRIPT = (_ASSETS / "ui.js").read_text(encoding="utf-8")
UI_STYLESHEET = (_ASSETS / "ui.css").read_text(encoding="utf-8")
