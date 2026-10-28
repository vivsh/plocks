"""Immutable images and explicit Pillow snapshot conversion."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, overload
from warnings import warn

import pygame
from PIL import Image as PillowImage
from PIL import ImageChops, ImageEnhance

from . import _shapes
from .errors import AssetError
from .geometry import Color, Point, _integer, _number, _point, _rotate


class Anchor(Enum):
    """Nine named attachment points for images and screen controls.

    CENTER is the default. Images resolve these once to top-left pixel coordinates;
    BOTTOM_CENTER makes an actor's position its feet. UI controls retain the named
    anchor as their content changes size. Images also accept precise pixel Points.
    """

    TOP_LEFT = (0.0, 0.0)
    TOP_CENTER = (0.5, 0.0)
    TOP_RIGHT = (1.0, 0.0)
    CENTER_LEFT = (0.0, 0.5)
    CENTER = (0.5, 0.5)
    CENTER_RIGHT = (1.0, 0.5)
    BOTTOM_LEFT = (0.0, 1.0)
    BOTTOM_CENTER = (0.5, 1.0)
    BOTTOM_RIGHT = (1.0, 1.0)


def _anchor(value: Anchor | Point | None, width: int, height: int) -> Point:
    if value is None:
        value = Anchor.CENTER
    if isinstance(value, Anchor):
        x, y = value.value
        return (width * x, height * y)
    if not isinstance(value, tuple) or len(value) != 2:
        raise TypeError("An anchor must be an Anchor or an (x, y) Point")
    return _point(value, "anchor")


@dataclass(frozen=True, init=False, eq=False)
class Image:
    """Owned RGBA pixels and an image-coordinate rotation/placement anchor.

    Pillow inputs are copied. Editing them later cannot change this image.
    Files support PNG, JPEG, and WebP. Missing or invalid images raise AssetError.
    Named anchors resolve to pixels once. Image inputs share immutable pixels and
    keep their anchor unless an explicit replacement is supplied.

    Args:
        source: An image, image file path, or Pillow image.
        anchor: The image point used for placement and rotation; default is center.
    """

    _pixels: pygame.Surface
    _anchor: Point

    def __init__(self, source: ImageSource, *, anchor: Anchor | Point | None = None) -> None:
        if isinstance(source, Image):
            object.__setattr__(self, "_pixels", source._pixels)
            point = (
                source.anchor if anchor is None else _anchor(anchor, source.width, source.height)
            )
            object.__setattr__(self, "_anchor", point)
            return
        try:
            if isinstance(source, PillowImage.Image):
                rgba = source.convert("RGBA")
            else:
                with PillowImage.open(source) as image:
                    if image.format not in {"PNG", "JPEG", "WEBP"}:
                        raise AssetError(f"Use PNG, JPEG, or WebP for {source}")
                    rgba = image.convert("RGBA")
            if rgba.width == 0 or rgba.height == 0:
                raise AssetError("An image must contain at least one pixel")
            pixels = pygame.image.frombytes(rgba.tobytes(), rgba.size, "RGBA")
        except (OSError, ValueError) as error:
            raise AssetError(f"Cannot read image {source!s}: {error}") from error
        object.__setattr__(self, "_pixels", pixels)
        object.__setattr__(self, "_anchor", _anchor(anchor, rgba.width, rgba.height))

    @staticmethod
    def rectangle(
        width: int,
        height: int,
        *,
        color: Color | None = "white",
        outline: Color | None = None,
        outline_width: int = 1,
        anchor: Anchor | Point | None = None,
    ) -> Image:
        """Make a rectangle with positive integer pixel dimensions, without a file.

        Color is the fill (white by default); None leaves it transparent. Optional
        outline stays inside the size, with positive integer outline_width pixels.
        Named colors and RGB/RGBA tuples work. The default anchor is CENTER.
        Invalid values raise ValueError; wrong types raise TypeError. No window
        is opened. Example: Sprite(Image.rectangle(80, 20, color="seagreen")).
        """
        pixels = _shapes.box("rectangle", width, height, color, outline, outline_width)
        return Image(pixels, anchor=anchor)

    @staticmethod
    def circle(
        radius: int,
        *,
        color: Color | None = "white",
        outline: Color | None = None,
        outline_width: int = 1,
        anchor: Anchor | Point | None = None,
    ) -> Image:
        """Make a circle, twice the positive integer radius in pixel width/height.

        Outside pixels are transparent. Color is the fill (white by default);
        None leaves a transparent center. Optional outline stays inside, with a
        positive integer outline_width. Named colors and RGB/RGBA tuples work.
        Anchor defaults to CENTER. Invalid values raise ValueError; wrong types
        raise TypeError. Example: ball = Sprite(Image.circle(16, color="gold")).
        Physics/collision shapes are configured separately, not inferred.
        """
        radius = _integer(radius, "radius", minimum=1)
        pixels = _shapes.box("ellipse", radius * 2, radius * 2, color, outline, outline_width)
        return Image(pixels, anchor=anchor)

    @staticmethod
    def ellipse(
        width: int,
        height: int,
        *,
        color: Color | None = "white",
        outline: Color | None = None,
        outline_width: int = 1,
        anchor: Anchor | Point | None = None,
    ) -> Image:
        """Make an oval inside positive integer pixel dimensions, without a file.

        Outside pixels are transparent. Color is the fill (white by default);
        None leaves it transparent. Optional outline stays inside the dimensions,
        with positive integer outline_width. Named colors and RGB/RGBA tuples
        work; anchor defaults to CENTER. Invalid values raise ValueError; wrong
        types raise TypeError. Example: Image.ellipse(48, 24, color="skyblue").
        """
        pixels = _shapes.box("ellipse", width, height, color, outline, outline_width)
        return Image(pixels, anchor=anchor)

    @staticmethod
    def triangle(
        width: int,
        height: int,
        *,
        color: Color | None = "white",
        outline: Color | None = None,
        outline_width: int = 1,
        anchor: Anchor | Point | None = None,
    ) -> Image:
        """Make an upward triangle inside positive integer pixel dimensions.

        Use rotated() for another direction. Outside pixels are transparent.
        Color is the fill (white by default); None leaves it transparent. Optional
        outline stays inside, with positive integer outline_width. Named colors
        and RGB/RGBA tuples work; anchor defaults to CENTER. Invalid values raise
        ValueError; wrong types raise TypeError. Example: Image.triangle(32, 40).
        """
        pixels = _shapes.box("triangle", width, height, color, outline, outline_width)
        return Image(pixels, anchor=anchor)

    @staticmethod
    def polygon(
        points: Iterable[Point],
        *,
        color: Color | None = "white",
        outline: Color | None = None,
        outline_width: int = 1,
        anchor: Anchor | Point | None = None,
    ) -> Image:
        """Make a tightly cropped simple polygon from at least three pixel points.

        Image coordinates go right/down. Finite points are floored to pixels,
        translated to top-left, and extreme pixels included: (0,0),(20,0),(10,10)
        gives 21x11. Negative coordinates and concave shapes work; collinear points
        fail and self-crossing paths are unsupported. The iterable is consumed
        once. Anchor refers to the result, CENTER by default. Color fills white;
        None leaves it transparent. Optional outline stays inside with positive
        integer outline_width. Colors accept names or RGB/RGBA tuples. Invalid
        values raise ValueError; wrong types raise TypeError.
        """
        return Image(_shapes.polygon(points, color, outline, outline_width), anchor=anchor)

    @property
    def width(self) -> int:
        """Source width in pixels, before any sprite scaling or rotation."""
        return self._pixels.get_width()

    @property
    def height(self) -> int:
        """Source height in pixels, before any sprite scaling or rotation."""
        return self._pixels.get_height()

    @property
    def anchor(self) -> Point:
        """Placement anchor from the image's top-left, with image y downward."""
        return self._anchor

    def flipped(self, *, horizontal: bool = False, vertical: bool = False) -> Image:
        """Return a mirrored image, moving its anchor with the pixels.

        Both flags may be combined. Neither flag returns this immutable image.
        The original is unchanged. Example: left = right.flipped(horizontal=True).
        Non-boolean flags raise TypeError.
        """
        if not isinstance(horizontal, bool) or not isinstance(vertical, bool):
            raise TypeError("horizontal and vertical must be booleans")
        if not horizontal and not vertical:
            return self
        image = self.to_pillow()
        x, y = self.anchor
        if horizontal:
            image = image.transpose(PillowImage.Transpose.FLIP_LEFT_RIGHT)
            x = self.width - x
        if vertical:
            image = image.transpose(PillowImage.Transpose.FLIP_TOP_BOTTOM)
            y = self.height - y
        return Image(image, anchor=(x, y))

    def cropped(self, x: int, y: int, width: int, height: int) -> Image:
        """Copy a rectangle in image pixels, measured right/down from top-left.

        The anchor moves by (-x, -y) and may lie outside the resulting image.
        Width/height must be positive and the crop must fit inside this image;
        invalid ranges raise ValueError, non-integer values raise TypeError.
        Example: portrait = sheet.cropped(x=0, y=0, width=32, height=32).
        """
        x = _integer(x, "x", minimum=0)
        y = _integer(y, "y", minimum=0)
        width = _integer(width, "width", minimum=1)
        height = _integer(height, "height", minimum=1)
        if x + width > self.width or y + height > self.height:
            raise ValueError("The crop must fit inside the image")
        image = self.to_pillow().crop((x, y, x + width, y + height))
        return Image(image, anchor=(self.anchor[0] - x, self.anchor[1] - y))

    def trimmed(self, *, color: Color | None = None) -> Image:
        """Remove transparent outer padding and, optionally, an exact border color.

        Keep the smallest rectangle containing pixels with nonzero alpha that
        differ from color. Names/RGB tuples mean opaque colors; RGBA tuples
        match all four channels exactly. Interior pixels are never recolored.
        With color=None, even faint outlines and shadows remain.

        The anchor shifts by the removed left/top padding, preserving artwork
        placement. An unchanged or entirely empty result returns this image.
        The original is immutable. Invalid colors raise TypeError or ValueError.
        Example: hero = Image("hero.png").trimmed(color="white").
        """
        rgba = _shapes._rgba(color)
        image = self.to_pillow()
        alpha = image.getchannel("A")
        if rgba is not None:
            difference = ImageChops.difference(image, PillowImage.new("RGBA", image.size, rgba))
            mask = difference.getchannel("R")
            for channel in ("G", "B", "A"):
                mask = ImageChops.lighter(mask, difference.getchannel(channel))
            # Saturate nonzero differences so even alpha-one outlines survive.
            mask = ImageEnhance.Brightness(mask).enhance(255)
            alpha = ImageChops.multiply(alpha, mask)
        bounds = alpha.getbbox()
        if bounds is None or bounds == (0, 0, self.width, self.height):
            return self
        left, top, right, bottom = bounds
        return self.cropped(left, top, right - left, bottom - top)

    @overload
    def with_anchor(self, anchor: Anchor | Point, /) -> Image: ...
    @overload
    def with_anchor(self, x: float, y: float) -> Image: ...
    def with_anchor(self, x: float | Anchor | Point, y: float | None = None) -> Image:
        """Return a new pivot sharing immutable pixels; the original is unchanged.

        Use image.with_anchor(Anchor.BOTTOM_CENTER), with_anchor((8, 4)), or
        with_anchor(x=8, y=4). Image coordinates start top-left, y downward.
        Precise anchors may lie outside the image; coordinates must be finite.
        """
        if y is None:
            if not isinstance(x, (Anchor, tuple)):
                raise TypeError("Supply an Anchor, a Point, or both x and y")
            point = _anchor(x, self.width, self.height)
        else:
            if isinstance(x, (Anchor, tuple)):
                raise TypeError("A named/tuple anchor cannot also supply y")
            point = _point((x, y), "anchor")
        return _from_pixels(self._pixels, point)

    def rotated(self, degrees: float) -> Image:
        """Return a clockwise rotation in degrees, moving the anchor with it.

        Rotate around the image center and expand with transparent padding to
        avoid clipping. Nearest-neighbor sampling preserves pixel-art colors.
        The original stays unchanged. Non-finite angles raise ValueError and
        non-numeric angles raise TypeError. Example: tile.rotated(90).
        """
        degrees = _number(degrees, "degrees") % 360
        image = self.to_pillow().rotate(
            -degrees, resample=PillowImage.Resampling.NEAREST, expand=True
        )
        x, y = self.anchor
        # Convert the image's downward y axis to world coordinates for rotation.
        dx, dy = _rotate((x - self.width / 2, self.height / 2 - y), 90 + degrees)
        return Image(image, anchor=(image.width / 2 + dx, image.height / 2 - dy))

    def resized(self, width: int, height: int) -> Image:
        """Return an exact pixel size, scaling the anchor with the image.

        Nearest-neighbor sampling keeps pixel art crisp. Changing the aspect ratio
        stretches the image. Dimensions must be positive integers; invalid values
        raise ValueError or TypeError. Example: tree.resized(width=32, height=64).
        """
        width = _integer(width, "width", minimum=1)
        height = _integer(height, "height", minimum=1)
        anchor = _point(
            (self.anchor[0] * (width / self.width), self.anchor[1] * (height / self.height)),
            "anchor",
        )
        pixels = pygame.transform.scale(self._pixels, (width, height))
        return _from_pixels(pixels, anchor)

    def to_pillow(self) -> PillowImage.Image:
        """Return an independent RGBA image; editing it leaves this asset unchanged."""
        return PillowImage.frombytes(
            "RGBA", (self.width, self.height), pygame.image.tobytes(self._pixels, "RGBA")
        )


type ImageSource = Image | str | Path | PillowImage.Image
"""An existing immutable image, filename, or Pillow image."""


def _from_pixels(pixels: pygame.Surface, anchor: Point) -> Image:
    """Wrap private immutable pixels and a validated anchor without copying them."""
    image = object.__new__(Image)
    object.__setattr__(image, "_pixels", pixels)
    object.__setattr__(image, "_anchor", anchor)
    return image


def _image(source: ImageSource) -> Image:
    return source if isinstance(source, Image) else Image(source)


@dataclass(frozen=True, init=False, eq=False)
class ImageGrid:
    """Pick pictures from rows and columns in one image.

    Each picture must have the same size, like frames in a walking animation.
    """

    _source: Image
    _frame_size: tuple[int, int]
    _margin: tuple[int, int]
    _spacing: tuple[int, int]

    def __init__(
        self,
        source: ImageSource,
        *,
        frame_size: tuple[int, int],
        margin: tuple[int, int] = (0, 0),
        spacing: tuple[int, int] = (0, 0),
    ) -> None:
        """Pick pictures from rows and columns in one image.

        Args:
            source: The image or filename holding your pictures.
            frame_size: Width and height of each picture, in pixels.
            margin: Pixels to skip at each outer edge, as (x, y). Default: (0, 0).
            spacing: Pixels to skip between pictures, as (x, y). Default: (0, 0).

        Raises:
            ValueError: The pictures do not fit in a complete grid.
            TypeError: The sizes are not integers.
        """
        frame = tuple(_integer(value, "frame_size", minimum=1) for value in frame_size)
        border = tuple(_integer(value, "margin", minimum=0) for value in margin)
        gap = tuple(_integer(value, "spacing", minimum=0) for value in spacing)
        if any(len(pair) != 2 for pair in (frame, border, gap)):
            raise ValueError("frame_size, margin, and spacing must each contain two integers")
        image = _image(source)
        for extent, size, edge, between in zip((image.width, image.height), frame, border, gap):
            usable = extent - 2 * edge + between
            if usable < size + between or usable % (size + between):
                raise ValueError("The image does not contain a complete image grid")
        object.__setattr__(self, "_source", image)
        object.__setattr__(self, "_frame_size", (frame[0], frame[1]))
        object.__setattr__(self, "_margin", (border[0], border[1]))
        object.__setattr__(self, "_spacing", (gap[0], gap[1]))

    @property
    def frame_size(self) -> tuple[int, int]:
        """Unscaled frame width and height in source pixels."""
        return self._frame_size

    @property
    def rows(self) -> int:
        """Number of complete rows, derived from the source grid."""
        return (self._source.height - 2 * self._margin[1] + self._spacing[1]) // (
            self._frame_size[1] + self._spacing[1]
        )

    @property
    def columns(self) -> int:
        """Number of complete columns, derived from the source grid."""
        return (self._source.width - 2 * self._margin[0] + self._spacing[0]) // (
            self._frame_size[0] + self._spacing[0]
        )

    def frame(self, *, row: int, column: int, anchor: Anchor | Point | None = None) -> Image:
        """Pick one picture from the grid.

        Args:
            row: Which row to use, counting from zero at the top.
            column: Which column to use, counting from zero on the left.
            anchor: Where the picture is held. The default is its center.

        Raises:
            IndexError: The row or column is outside the grid.
            TypeError: The row or column is not an integer.
        """
        _integer(row, "row")
        _integer(column, "column")
        if not 0 <= row < self.rows or not 0 <= column < self.columns:
            raise IndexError(f"Frame ({row}, {column}) is outside {self.rows}x{self.columns}")
        width, height = self.frame_size
        x = self._margin[0] + column * (width + self._spacing[0])
        y = self._margin[1] + row * (height + self._spacing[1])
        image = self._source.to_pillow().crop((x, y, x + width, y + height))
        return Image(image, anchor=anchor)

    def frames(
        self, *, row: int | None = None, anchor: Anchor | Point | None = None
    ) -> tuple[Image, ...]:
        """Pick all pictures in a row, or every picture in the grid.

        Args:
            row: A row number starting at zero. Omit it for the whole grid.
            anchor: Where each picture is held. The default is its center.

        Pictures are returned left to right, then top to bottom. You can slice
        the tuple to choose fewer pictures. Invalid row numbers raise IndexError.
        """
        if row is not None:
            _integer(row, "row")
            if not 0 <= row < self.rows:
                raise IndexError(f"Row {row} is outside the image grid")
        rows = range(self.rows) if row is None else (row,)
        return tuple(
            self.frame(row=r, column=c, anchor=anchor) for r in rows for c in range(self.columns)
        )


# Static aliases preserve constructor signatures and exact runtime type identity.
if TYPE_CHECKING:
    Costume = Image
    SpriteSheet = ImageGrid

type CostumeSource = ImageSource
"""Deprecated: use ImageSource. Includes immutable Image, path and Pillow inputs."""


def _legacy_asset(name: str) -> type[Image | ImageGrid]:
    """Resolve the two deprecated asset names without wrapping their classes."""
    if name == "Costume":
        warn("Costume is deprecated; use Image", DeprecationWarning, stacklevel=2)
        return Image
    if name == "SpriteSheet":
        warn("SpriteSheet is deprecated; use ImageGrid", DeprecationWarning, stacklevel=2)
        return ImageGrid
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if not TYPE_CHECKING:
    __getattr__ = _legacy_asset


__all__ = ("Anchor", "Costume", "CostumeSource", "Image", "ImageGrid", "ImageSource", "SpriteSheet")
