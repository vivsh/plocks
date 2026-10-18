"""Editable finite tile worlds and repeating stage-coordinate backgrounds."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from .stage import Stage

from collections.abc import Iterable, Mapping, Sequence
from math import ceil, floor
from types import MappingProxyType

from .geometry import Bounds, Point, _integer, _number, _point
from .imaging import Costume, CostumeSource, _costume

type TileRows = Sequence[str] | Sequence[Sequence[str | None]]


class TileMap:
    """A rectangular character grid or explicit key matrix, placed by world top-left x/y.

    Cells select a shared costume palette. Tile dimensions and palette stay fixed;
    edit cells with set_tile. Solid cells participate in overlap queries and an enabled stage physics world.
    Nonphysical movement is never resolved automatically. Empty cells return None.
    """

    __slots__ = (
        "_cells",
        "_layer",
        "_opacity",
        "_palette",
        "_parallax",
        "_parallax_origin",
        "_solid",
        "_stage",
        "_tile_size",
        "_visible",
        "_x",
        "_y",
    )

    def __init__(
        self,
        rows: TileRows,
        palette: Mapping[str, CostumeSource],
        *,
        tile_size: tuple[int, int],
        solid: Iterable[str] = (),
        empty: str = ".",
        x: float = 0,
        y: float = 0,
        visible: bool = True,
        layer: int = 0,
        opacity: float = 1.0,
        parallax: Point = (1.0, 1.0),
        parallax_origin: Point = (0.0, 0.0),
    ) -> None:
        if not isinstance(empty, str) or len(empty) != 1:
            raise ValueError("empty must be one character")
        if not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
            raise ValueError("TileMap requires nonempty rows of equal length")
        character_rows = all(isinstance(row, str) for row in rows)
        if not character_rows and (any(isinstance(row, str) for row in rows) or empty != "."):
            raise ValueError(
                "Use either character rows or explicit matrix rows with None for empty"
            )
        if any(
            not isinstance(key, str)
            or not key
            or (character_rows and (len(key) != 1 or key == empty))
            for key in palette
        ):
            raise ValueError(
                "Palette keys must be nonempty strings; character grids require single characters"
            )
        self._palette: Mapping[str, Costume] = MappingProxyType(
            {key: _costume(value) for key, value in palette.items()}
        )
        self._solid = frozenset(solid)
        if not self._solid <= self._palette.keys():
            raise KeyError("Every solid tile key must exist in the palette")
        cells = (
            [[None if key == empty else key for key in row] for row in cast(Sequence[str], rows)]
            if character_rows
            else [list(row) for row in rows]
        )
        for row in cells:
            if any(
                key is not None and (not isinstance(key, str) or key not in self._palette)
                for key in row
            ):
                raise KeyError("The map contains a key absent from the palette")
        self.opacity = opacity
        self.parallax = parallax
        self.parallax_origin = parallax_origin
        self._stage: Stage | None = None
        self._cells = cells
        self._tile_size = (
            _integer(tile_size[0], "tile width", minimum=1),
            _integer(tile_size[1], "tile height", minimum=1),
        )
        self._x = _number(x, "x")
        self._y = _number(y, "y")
        self._visible = visible
        self._layer = _integer(layer, "layer")

    @property
    def opacity(self) -> float:
        """Drawing alpha in [0, 1]; transparent cells still collide when solid."""
        return self._opacity

    @opacity.setter
    def opacity(self, value: float) -> None:
        value = _number(value, "opacity", minimum=0)
        if value > 1:
            raise ValueError("opacity must be at most 1")
        self._opacity = value

    @property
    def parallax(self) -> Point:
        """Nonnegative camera factors; solid maps require (1, 1)."""
        return self._parallax

    @parallax.setter
    def parallax(self, value: Point) -> None:
        x, y = _point(value, "parallax")
        if x < 0 or y < 0 or (self.solid and (x, y) != (1, 1)):
            raise ValueError("Parallax must be nonnegative; solid maps require (1, 1)")
        self._parallax = (x, y)

    @property
    def parallax_origin(self) -> Point:
        """World-coordinate origin used to derive the effective drawing camera."""
        return self._parallax_origin

    @parallax_origin.setter
    def parallax_origin(self, value: Point) -> None:
        self._parallax_origin = _point(value, "parallax_origin")

    @property
    def rows(self) -> int:
        """Fixed number of rows, increasing downward."""
        return len(self._cells)

    @property
    def columns(self) -> int:
        """Fixed number of columns, increasing rightward."""
        return len(self._cells[0])

    @property
    def tile_size(self) -> tuple[int, int]:
        """Fixed logical cell width and height; costumes are fitted to these dimensions."""
        return self._tile_size

    @property
    def palette(self) -> Mapping[str, Costume]:
        """Read-only shared costumes addressed by nonempty string keys."""
        return self._palette

    @property
    def solid(self) -> frozenset[str]:
        """Read-only keys whose occupied cells participate in solid overlap queries."""
        return self._solid

    @property
    def cells(self) -> tuple[tuple[str | None, ...], ...]:
        """A snapshot for inspection; edit the authoritative grid through set_tile."""
        return tuple(tuple(row) for row in self._cells)

    @property
    def x(self) -> float:
        """World x of the map's left edge."""
        return self._x

    @x.setter
    def x(self, value: float) -> None:
        value = _number(value, "x")
        if self._stage is not None and self._stage._physics is not None:
            from ._physics import _terrain

            _terrain(self._stage._physics, self, position=(value, self.y))
        self._x = value

    @property
    def y(self) -> float:
        """World y of the map's top edge; rows extend downward from it."""
        return self._y

    @y.setter
    def y(self, value: float) -> None:
        value = _number(value, "y")
        if self._stage is not None and self._stage._physics is not None:
            from ._physics import _terrain

            _terrain(self._stage._physics, self, position=(self.x, value))
        self._y = value

    @property
    def position(self) -> Point:
        """The map's top-left world position, equivalent to (x, y)."""
        return self.x, self.y

    @position.setter
    def position(self, value: Point) -> None:
        point = _point(value)
        if self._stage is not None and self._stage._physics is not None:
            from ._physics import _terrain

            _terrain(self._stage._physics, self, position=point)
        self._x, self._y = point

    @property
    def visible(self) -> bool:
        """Whether cells are drawn; solid queries remain active when hidden."""
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self._visible = value

    @property
    def layer(self) -> int:
        """Draw order relative to other stage objects, with insertion-order ties."""
        return self._layer

    @layer.setter
    def layer(self, value: int) -> None:
        self._layer = _integer(value, "layer")

    @property
    def bounds(self) -> Bounds:
        """Bounds of the complete grid, including empty cells."""
        width, height = self.tile_size
        return Bounds(self.x, self.y - self.rows * height, self.x + self.columns * width, self.y)

    def _check_cell(self, row: int, column: int) -> None:
        _integer(row, "row")
        _integer(column, "column")
        if not 0 <= row < self.rows or not 0 <= column < self.columns:
            raise IndexError(f"Cell ({row}, {column}) is outside {self.rows}x{self.columns}")

    def get_tile(self, *, row: int, column: int) -> str | None:
        """Read a palette key or None. Negative/outside indices raise IndexError."""
        self._check_cell(row, column)
        return self._cells[row][column]

    def set_tile(self, *, row: int, column: int, tile: str | None) -> None:
        """Replace one cell. None clears it; unknown palette keys raise KeyError."""
        self._check_cell(row, column)
        if tile is not None and tile not in self.palette:
            raise KeyError(f"Unknown tile key: {tile}")
        if self._stage is not None and self._stage._physics is not None:
            from ._physics import _terrain

            cells = [line.copy() for line in self._cells]
            cells[row][column] = tile
            _terrain(self._stage._physics, self, cells=cells)
        self._cells[row][column] = tile

    def cell_at(self, *, x: float, y: float) -> tuple[int, int] | None:
        """Find (row, column) under a world point; right/bottom outer edges are outside."""
        x, y = _point((x, y))
        width, height = self.tile_size
        row, column = floor((self.y - y) / height), floor((x - self.x) / width)
        return (row, column) if 0 <= row < self.rows and 0 <= column < self.columns else None

    def tiles_touching(
        self, bounds: Bounds, *, solid_only: bool = True
    ) -> tuple[tuple[int, int], ...]:
        """Return occupied overlapping cells in row-major order, with positive overlap only."""
        if not self.bounds.intersects(bounds):
            return ()
        width, height = self.tile_size
        left = max(0, floor((bounds.left - self.x) / width))
        right = min(self.columns, ceil((bounds.right - self.x) / width))
        top = max(0, floor((self.y - bounds.top) / height))
        bottom = min(self.rows, ceil((self.y - bounds.bottom) / height))
        return tuple(
            (row, column)
            for row in range(top, bottom)
            for column in range(left, right)
            if (key := self._cells[row][column]) is not None
            and (not solid_only or key in self.solid)
        )


class TiledBackground:
    """Repeat a costume in stage coordinates, independent of the world camera.

    area=None fills the viewport. Offset shifts the pattern in logical pixels,
    with positive y upward. Derive offset from camera yourself for parallax.
    """

    __slots__ = ("_area", "_costume", "_layer", "_offset", "_visible")

    def __init__(
        self,
        source: CostumeSource,
        *,
        area: Bounds | None = None,
        offset: Point = (0, 0),
        visible: bool = True,
        layer: int = -100,
    ) -> None:
        self._costume = _costume(source)
        self._area = area
        self._offset = _point(offset, "offset")
        self._visible = visible
        self._layer = _integer(layer, "layer")

    @property
    def costume(self) -> Costume:
        """The immutable repeated image."""
        return self._costume

    @costume.setter
    def costume(self, value: CostumeSource) -> None:
        self._costume = _costume(value)

    @property
    def area(self) -> Bounds | None:
        """Stage-coordinate fill area; None follows viewport bounds."""
        return self._area

    @area.setter
    def area(self, value: Bounds | None) -> None:
        self._area = value

    @property
    def offset(self) -> Point:
        """Pattern shift; positive x moves right, positive y moves up."""
        return self._offset

    @offset.setter
    def offset(self, value: Point) -> None:
        self._offset = _point(value, "offset")

    @property
    def visible(self) -> bool:
        """Whether this repeating layer is drawn."""
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self._visible = value

    @property
    def layer(self) -> int:
        """Drawing layer; defaults to -100, behind ordinary objects."""
        return self._layer

    @layer.setter
    def layer(self, value: int) -> None:
        self._layer = _integer(value, "layer")
