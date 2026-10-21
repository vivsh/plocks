"""Operation-local raster drawing for immutable Image factories."""

from collections.abc import Iterable
from math import floor
from typing import Literal

import pygame
from PIL import Image as PillowImage
from PIL import ImageChops, ImageDraw

from .geometry import Color, Point, _integer, _point


def _rgba(color: Color | None) -> tuple[int, int, int, int] | None:
    """Validate the public color vocabulary without opening native resources."""
    if color is None:
        return None
    if isinstance(color, tuple):
        if len(color) not in (3, 4):
            raise ValueError("A color needs three RGB or four RGBA channels")
        for channel in color:
            if _integer(channel, "color channel", minimum=0) > 255:
                raise ValueError("Color channels must be between 0 and 255")
    elif not isinstance(color, str):
        raise TypeError("A color must be a name, an RGB/RGBA tuple, or None")
    value = pygame.Color(color)
    return (value.r, value.g, value.b, value.a)


def _paint(
    mask: PillowImage.Image,
    border: PillowImage.Image,
    color: Color | None,
    outline: Color | None,
) -> PillowImage.Image:
    """Apply independent fill/outline alpha, clipping the outline inside the shape."""
    fill, stroke = _rgba(color), _rgba(outline)
    image = PillowImage.new("RGBA", mask.size)
    if fill is not None:
        image.paste(fill, mask=mask)
    if stroke is not None:
        image.paste(stroke, mask=ImageChops.multiply(mask, border))
    return image


def box(
    kind: Literal["rectangle", "ellipse", "triangle"],
    width: int,
    height: int,
    color: Color | None,
    outline: Color | None,
    outline_width: int,
) -> PillowImage.Image:
    """Draw a pixel-sized primitive; every mask and drawing object is local."""
    width = _integer(width, "width", minimum=1)
    height = _integer(height, "height", minimum=1)
    thickness = min(_integer(outline_width, "outline_width", minimum=1), max(width, height))
    if kind == "triangle":
        points = [(width // 2, 0), (width - 1, height - 1), (0, height - 1)]
        return _polygon_image(points, (width, height), color, outline, thickness)
    mask = PillowImage.new("L", (width, height))
    border = PillowImage.new("L", (width, height))
    bounds = (0, 0, width - 1, height - 1)
    if kind == "rectangle" or min(width, height) == 1:
        ImageDraw.Draw(mask).rectangle(bounds, fill=255)
        ImageDraw.Draw(border).rectangle(bounds, outline=255, width=thickness)
    else:
        ImageDraw.Draw(mask).ellipse(bounds, fill=255)
        ImageDraw.Draw(border).ellipse(bounds, outline=255, width=thickness)
    return _paint(mask, border, color, outline)


def polygon(
    points: Iterable[Point],
    color: Color | None,
    outline: Color | None,
    outline_width: int,
) -> PillowImage.Image:
    """Consume finite vertices once, then draw a tight, translated pixel footprint."""
    thickness = _integer(outline_width, "outline_width", minimum=1)
    vertices: list[tuple[int, int]] = []
    for value in points:
        if not isinstance(value, tuple) or len(value) != 2:
            raise TypeError("Each polygon point must be an (x, y) tuple")
        x, y = _point(value, "polygon point")
        vertices.append((floor(x), floor(y)))
    if len(vertices) < 3:
        raise ValueError("A polygon needs at least three noncollinear pixel points")
    edges = list(zip(vertices, vertices[1:] + vertices[:1]))
    if sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in edges) == 0:
        raise ValueError("A polygon needs at least three noncollinear pixel points")
    left, top = min(x for x, _ in vertices), min(y for _, y in vertices)
    width = max(x for x, _ in vertices) - left + 1
    height = max(y for _, y in vertices) - top + 1
    translated = [(x - left, y - top) for x, y in vertices]
    return _polygon_image(
        translated, (width, height), color, outline, min(thickness, max(width, height))
    )


def _polygon_image(
    points: list[tuple[int, int]],
    size: tuple[int, int],
    color: Color | None,
    outline: Color | None,
    thickness: int,
) -> PillowImage.Image:
    """Clip a doubled boundary stroke to the filled mask for an inward outline."""
    mask = PillowImage.new("L", size)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    border = PillowImage.new("L", size)
    ImageDraw.Draw(border).line(
        points + points[:1], fill=255, width=2 * thickness - 1, joint="curve"
    )
    return _paint(mask, border, color, outline)
