"""Independent playback, exact frame transitions, and spritesheet input contracts."""

import pytest
from PIL import Image as PillowImage
from PIL import ImageDraw

from plocks import Image, ImageGrid


def images() -> tuple[Image, ...]:
    """Create three distinguishable immutable teaching frames."""
    return tuple(
        Image(PillowImage.new("RGBA", (2, 2), color)) for color in ("red", "green", "blue")
    )


def test_grid_margins_spacing_and_order() -> None:
    """Grid extraction addresses rows/columns, honors spacing, and owns copied pixels."""
    image = PillowImage.new("RGBA", (7, 7))
    draw = ImageDraw.Draw(image)
    colors = ("red", "blue", "green", "white")
    for (x, y), color in zip(((1, 1), (4, 1), (1, 4), (4, 4)), colors):
        draw.rectangle((x, y, x + 1, y + 1), fill=color)
    sheet = ImageGrid(image, frame_size=(2, 2), margin=(1, 1), spacing=(1, 1))
    assert (sheet.rows, sheet.columns) == (2, 2)
    assert [frame.to_pillow().getpixel((0, 0)) for frame in sheet.frames()] == [
        (255, 0, 0, 255),
        (0, 0, 255, 255),
        (0, 128, 0, 255),
        (255, 255, 255, 255),
    ]
    image.paste("black", (0, 0, 7, 7))
    assert sheet.frame(row=0, column=0).to_pillow().getpixel((0, 0)) == (255, 0, 0, 255)
    assert len(sheet.frames(row=1)) == 2
    with pytest.raises(IndexError):
        sheet.frame(row=-1, column=0)
    with pytest.raises(IndexError):
        sheet.frames(row=2)
    with pytest.raises(ValueError):
        ImageGrid(image, frame_size=(3, 3))
