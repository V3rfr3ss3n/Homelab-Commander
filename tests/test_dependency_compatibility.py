"""Exercise the HA/Pillow boundary changed by the security replacement."""

from io import BytesIO
from pathlib import Path

import pytest
from homeassistant.util.pil import draw_box
from PIL import Image, ImageDraw


@pytest.mark.parametrize("image_format", ["PNG", "JPEG"])
def test_home_assistant_image_annotation_survives_secure_pillow_replacement(
    image_format: str,
) -> None:
    """HA annotation, image codecs and resizing work with the fixed dependency."""
    source = Image.new("RGB", (160, 100), "white")
    encoded = BytesIO()
    source.save(encoded, format=image_format)
    encoded.seek(0)
    with Image.open(encoded) as image:
        image.load()
        draw_box(
            ImageDraw.Draw(image),
            (0.2, 0.2, 0.8, 0.8),
            image.width,
            image.height,
            text="node-01",
        )
        assert image.getpixel((32, 20)) == (255, 255, 0)
        image.thumbnail((80, 80))
        assert image.size == (80, 50)
        result = BytesIO()
        image.save(result, format=image_format)
    result.seek(0)
    with Image.open(result) as restored:
        restored.load()
        assert restored.size == (80, 50)
        assert restored.format == image_format


def test_shipped_brand_image_decodes_and_resizes() -> None:
    """The replacement still handles the integration's actual public asset."""
    icon = (
        Path(__file__).parents[1] / "custom_components/homelab_updates/brand/icon.png"
    )
    with Image.open(icon) as image:
        image.load()
        assert image.size == (256, 256)
        image.thumbnail((64, 64))
        assert image.size == (64, 64)
