"""HA schema engines must not break existing installation compatibility."""

import builtins
import runpy
import sys
from pathlib import Path

import probatio
import pytest
import voluptuous

from custom_components.homelab_updates.schema import schema

SCHEMA_PATH = Path(__file__).parents[1] / "custom_components/homelab_updates/schema.py"


def test_current_home_assistant_uses_probatio() -> None:
    """Forms and WS markers must use HA's current validation engine."""
    assert schema is probatio
    validator = schema.Schema({schema.Required("entry_id"): str})
    assert validator({"entry_id": "synthetic-entry"}) == {"entry_id": "synthetic-entry"}
    with pytest.raises(schema.Invalid):
        validator({})


def test_older_home_assistant_retains_voluptuous(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An absent Probatio uses the previous engine with unchanged validation."""
    monkeypatch.setitem(sys.modules, "probatio", None)
    namespace = runpy.run_path(str(SCHEMA_PATH))
    legacy = namespace["schema"]
    assert legacy is voluptuous
    validator = legacy.Schema({legacy.Required("entry_id"): str})
    assert validator({"entry_id": "synthetic-entry"}) == {"entry_id": "synthetic-entry"}
    with pytest.raises(voluptuous.Invalid):
        validator({})


def test_broken_probatio_dependency_does_not_silently_switch_engines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the engine's absence is recoverable, not an internal import error."""
    original = builtins.__import__

    def broken_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "probatio":
            raise ModuleNotFoundError("Synthetic missing dependency", name="synthetic")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken_import)
    with pytest.raises(ModuleNotFoundError, match="Synthetic missing dependency"):
        runpy.run_path(str(SCHEMA_PATH))
