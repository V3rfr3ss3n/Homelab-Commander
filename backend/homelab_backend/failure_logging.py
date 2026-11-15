"""Standard-library-only safe logging shared by API and application services."""

import logging
import traceback
from pathlib import Path

_LOGGER = logging.getLogger(__name__)


def log_internal_failure(error: Exception, reference: str, operation: str) -> None:
    """Keep useful code locations, never exception text, locals or source lines."""
    frames = traceback.extract_tb(error.__traceback__)[-6:]
    locations = ",".join(
        f"{Path(frame.filename).name}:{frame.lineno}" for frame in frames
    )
    _LOGGER.error(
        "Internal failure reference=%s operation=%s locations=%s",
        reference,
        operation,
        locations,
    )
