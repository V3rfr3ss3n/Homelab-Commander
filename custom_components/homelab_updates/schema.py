"""Use HA's schema engine while retaining pre-Probatio installations."""

from typing import TYPE_CHECKING

__all__ = ["schema"]

if TYPE_CHECKING:
    import probatio as schema
else:
    try:
        import probatio as schema
    except ModuleNotFoundError as err:
        if err.name != "probatio":
            raise
        import voluptuous as schema
