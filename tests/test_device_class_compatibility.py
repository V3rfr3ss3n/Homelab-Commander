"""Retain the advertised HA minimum through device-class module changes."""

import builtins
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest
from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
from homeassistant.components.button.const import ButtonDeviceClass

from custom_components.homelab_updates import device_classes

COMPAT_PATH = (
    Path(__file__).parents[1] / "custom_components/homelab_updates/device_classes.py"
)


def test_current_device_classes_use_explicit_exports() -> None:
    """The tested current HA baseline keeps the same restart/connectivity values."""
    assert device_classes.BinarySensorDeviceClass is BinarySensorDeviceClass
    assert device_classes.ButtonDeviceClass is ButtonDeviceClass


def test_legacy_device_classes_remain_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Older HA lacks the binary module and the button module's class export."""
    original = builtins.__import__

    def legacy_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "homeassistant.components.binary_sensor.const":
            raise ModuleNotFoundError("Synthetic old HA module", name=name)
        if name == "homeassistant.components.button.const":
            raise ImportError("Synthetic old HA export", name=name)
        if name == "homeassistant.components.binary_sensor":
            return SimpleNamespace(BinarySensorDeviceClass=BinarySensorDeviceClass)
        if name == "homeassistant.components.button":
            return SimpleNamespace(ButtonDeviceClass=ButtonDeviceClass)
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", legacy_import)
    namespace = runpy.run_path(str(COMPAT_PATH))
    assert namespace["BinarySensorDeviceClass"] is BinarySensorDeviceClass
    assert namespace["ButtonDeviceClass"] is ButtonDeviceClass


@pytest.mark.parametrize(
    "module",
    [
        "homeassistant.components.binary_sensor.const",
        "homeassistant.components.button.const",
    ],
)
def test_unrelated_dependency_import_errors_are_not_hidden(
    monkeypatch: pytest.MonkeyPatch, module: str
) -> None:
    """An internally broken framework import must not silently select a fallback."""
    original = builtins.__import__

    def broken_import(name: str, *args: object, **kwargs: object) -> object:
        if name == module:
            raise ImportError("Synthetic broken framework dependency", name="synthetic")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken_import)
    with pytest.raises(ImportError, match="Synthetic broken framework dependency"):
        runpy.run_path(str(COMPAT_PATH))
