"""Immutable image costumes and explicit Pillow snapshot conversion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pygame
from PIL import Image

from .errors import AssetError
from .geometry import Point, _integer, _point

type ImageSource = str | Path | Image.Image
"""An image filename or an already-created Pillow image."""


@dataclass(frozen=True, init=False, eq=False)
class Costume:
    """Owned RGBA pixels and an image-coordinate rotation/placement anchor.

    Pillow inputs are copied. Editing them later cannot change this costume.
    Files support PNG, JPEG, and WebP. Missing or invalid images raise AssetError.
    """

    _pixels: pygame.Surface
    _anchor: Point

    def __init__(self, source: ImageSource, *, anchor: Point | None = None) -> None:
        try:
            if isinstance(source, Image.Image):
                rgba = source.convert("RGBA")
            else:
                with Image.open(source) as image:
                    if image.format not in {"PNG", "JPEG", "WEBP"}:
                        raise AssetError(f"Use PNG, JPEG, or WebP for {source}")
                    rgba = image.convert("RGBA")
            if rgba.width == 0 or rgba.height == 0:
                raise AssetError("A costume must contain at least one pixel")
            pixels = pygame.image.frombytes(rgba.tobytes(), rgba.size, "RGBA")
        except (OSError, ValueError) as error:
            raise AssetError(f"Cannot read image {source!s}: {error}") from error
        object.__setattr__(self, "_pixels", pixels)
        default = (rgba.width / 2, rgba.height / 2)
        object.__setattr__(self, "_anchor", _point(default if anchor is None else anchor, "anchor"))

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

    def to_pillow(self) -> Image.Image:
        """Return an independent RGBA image; editing it leaves this asset unchanged."""
        return Image.frombytes(
            "RGBA", (self.width, self.height), pygame.image.tobytes(self._pixels, "RGBA")
        )


type CostumeSource = Costume | ImageSource
"""An existing immutable costume, filename, or Pillow image."""


def _costume(source: CostumeSource) -> Costume:
    return source if isinstance(source, Costume) else Costume(source)


@dataclass(frozen=True, init=False, eq=False)
class SpriteSheet:
    """A complete rectangular grid of costumes, addressed by row and column.

    Margins surround all four sides; spacing separates frames. Dimensions must
    fit a complete grid. Extracting a frame copies its pixels; no cache is kept.
    """

    _source: Costume
    _frame_size: tuple[int, int]
    _margin: tuple[int, int]
    _spacing: tuple[int, int]

    def __init__(
        self,
        source: CostumeSource,
        *,
        frame_size: tuple[int, int],
        margin: tuple[int, int] = (0, 0),
        spacing: tuple[int, int] = (0, 0),
    ) -> None:
        frame = tuple(_integer(value, "frame_size", minimum=1) for value in frame_size)
        border = tuple(_integer(value, "margin", minimum=0) for value in margin)
        gap = tuple(_integer(value, "spacing", minimum=0) for value in spacing)
        if any(len(pair) != 2 for pair in (frame, border, gap)):
            raise ValueError("frame_size, margin, and spacing must each contain two integers")
        costume = _costume(source)
        for extent, size, edge, between in zip((costume.width, costume.height), frame, border, gap):
            usable = extent - 2 * edge + between
            if usable < size + between or usable % (size + between):
                raise ValueError("The image does not contain a complete spritesheet grid")
        object.__setattr__(self, "_source", costume)
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

    def frame(self, *, row: int, column: int, anchor: Point | None = None) -> Costume:
        """Copy one frame. Row/column start at zero; invalid indexes raise IndexError."""
        _integer(row, "row")
        _integer(column, "column")
        if not 0 <= row < self.rows or not 0 <= column < self.columns:
            raise IndexError(f"Frame ({row}, {column}) is outside {self.rows}x{self.columns}")
        width, height = self.frame_size
        x = self._margin[0] + column * (width + self._spacing[0])
        y = self._margin[1] + row * (height + self._spacing[1])
        image = self._source.to_pillow().crop((x, y, x + width, y + height))
        return Costume(image, anchor=anchor)

    def frames(self, *, row: int | None = None) -> tuple[Costume, ...]:
        """Return a row, or all frames in row-major order. Slice the returned tuple."""
        if row is not None:
            _integer(row, "row")
            if not 0 <= row < self.rows:
                raise IndexError(f"Row {row} is outside the spritesheet")
        rows = range(self.rows) if row is None else (row,)
        return tuple(self.frame(row=r, column=c) for r in rows for c in range(self.columns))
