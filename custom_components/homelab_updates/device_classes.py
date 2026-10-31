"""Keep device classes available across HA's explicit-export migration."""

from typing import TYPE_CHECKING

__all__ = ["BinarySensorDeviceClass", "ButtonDeviceClass"]

if TYPE_CHECKING:
    from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
    from homeassistant.components.button.const import ButtonDeviceClass
else:
    try:
        from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
    except ImportError as err:
        if err.name != "homeassistant.components.binary_sensor.const":
            raise
        from homeassistant.components.binary_sensor import BinarySensorDeviceClass

    try:
        from homeassistant.components.button.const import ButtonDeviceClass
    except ImportError as err:
        if err.name != "homeassistant.components.button.const":
            raise
        from homeassistant.components.button import ButtonDeviceClass
