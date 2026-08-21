"""Local Home Assistant brand asset tests."""

from pathlib import Path
from struct import unpack

import pytest

BRAND_DIR = (
    Path(__file__).parents[1] / "custom_components" / "homelab_updates" / "brand"
)


@pytest.mark.parametrize(
    ("filename", "expected_size"),
    [("icon.png", 256), ("icon@2x.png", 512)],
)
def test_brand_icon_is_square_rgba_png(filename: str, expected_size: int) -> None:
    """Brand icons have the exact dimensions and alpha channel HA expects."""
    data = (BRAND_DIR / filename).read_bytes()

    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert unpack(">II", data[16:24]) == (expected_size, expected_size)
    assert data[25] == 6
