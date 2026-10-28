"""Editable finite tile worlds and repeating stage-coordinate backgrounds."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast

if TYPE_CHECKING:
    from ._commands import Actor
    from .stage import Stage

from collections.abc import Iterable, Mapping, Sequence
from math import ceil, floor
from types import MappingProxyType

from typing_extensions import deprecated

from .geometry import Bounds, Point, _integer, _number, _point
from .imaging import Image, ImageSource, _image

type TileRows = Sequence[str] | Sequence[Sequence[str | None]]


class TileMap:
    """A rectangular character grid or explicit key matrix, placed by world top-left x/y.

    Cells select a shared image palette. Tile dimensions and palette stay fixed;
    edit cells with set_tile. Solid cells participate in overlap queries and an enabled stage physics world.
    one_way keys support landing from above, allowing jumps through from below.
    Solid and one-way keys must be disjoint. Nonphysical movement is never resolved
    automatically. Empty cells return None.
    """

    __slots__ = (
        "_cells",
        "_layer",
        "_one_way",
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
        palette: Mapping[str, ImageSource],
        *,
        tile_size: tuple[int, int],
        solid: Iterable[str] = (),
        one_way: Iterable[str] = (),
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
        self._palette: Mapping[str, Image] = MappingProxyType(
            {key: _image(value) for key, value in palette.items()}
        )
        self._solid = frozenset(solid)
        if not self._solid <= self._palette.keys():
            raise KeyError("Every solid tile key must exist in the palette")
        self._one_way = frozenset(one_way)
        if not self._one_way <= self._palette.keys():
            raise KeyError("Every one-way tile key must exist in the palette")
        if self._solid & self._one_way:
            raise ValueError("A tile key cannot be both solid and one-way")
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
        """Nonnegative camera factors; solid maps and one-way maps require (1, 1)."""
        return self._parallax

    @parallax.setter
    def parallax(self, value: Point) -> None:
        x, y = _point(value, "parallax")
        if x < 0 or y < 0 or ((self.solid or self.one_way) and (x, y) != (1, 1)):
            raise ValueError(
                "Parallax must be nonnegative; solid maps and one-way maps require (1, 1)"
            )
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
        """Fixed logical cell width and height; images are fitted to these dimensions."""
        return self._tile_size

    @property
    def palette(self) -> Mapping[str, Image]:
        """Read-only shared images addressed by nonempty string keys."""
        return self._palette

    @property
    def solid(self) -> frozenset[str]:
        """Read-only tile keys that block physical actors from every side."""
        return self._solid

    @property
    def one_way(self) -> frozenset[str]:
        """Read-only keys for platforms that support falling actors from above only.

        Physics requires Stage(physics=True). Geometric overlap queries include
        these cells from either side; body contacts include accepted landings only.
        Keys must exist in the palette and cannot also appear in solid.
        """
        return self._one_way

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

    def cell_center(self, *, row: int, column: int) -> Point:
        """Return a cell's world center. Rows/columns are zero-based from top-left."""
        self._check_cell(row, column)
        w, h = self.tile_size
        return _point((self.x + (column + 0.5) * w, self.y - (row + 0.5) * h))

    def find_path(
        self, *, start: Point, goal: Point, actor: Actor | None = None, max_nodes: int = 10_000
    ) -> tuple[Point, ...] | None:
        """Find a four-direction route around solid/one-way tiles in world coordinates.

        Supply actor to check its current visual footprint; otherwise plan for a
        point. Returns immutable waypoints or None when unreachable. Outside or
        invalid endpoints raise ValueError; budget exhaustion raises NavigationError.
        Map edits/moving actors do not update a returned route. No stage is needed.
        """
        from ._navigation import _find

        return _find(self, start, goal, actor, max_nodes)

    def join(self, other: TileMap, *, direction: Literal["right", "down"]) -> TileMap:
        """Make a new map by joining another section to the right or below.

        Right requires equal row counts; down requires equal column counts.
        Tile sizes must match. Shared palette keys must have identical RGBA
        pixels and matching solid/one-way behavior. Disjoint keys are combined.
        The new map takes its position, visibility, layer, opacity and parallax
        from this map; other.position and drawing settings do not affect it.
        Both originals stay unchanged and the result is not added to a stage.
        Invalid directions, sizes or conflicting keys raise ValueError.
        Example: level = start.join(middle, direction="right").
        """
        if not isinstance(other, TileMap):
            raise TypeError("Join another TileMap")
        if direction not in ("right", "down"):
            raise ValueError("direction must be 'right' or 'down'")
        if self.tile_size != other.tile_size:
            raise ValueError("Joined maps must use the same tile size")
        if direction == "right" and self.rows != other.rows:
            raise ValueError("Maps joined to the right must have the same number of rows")
        if direction == "down" and self.columns != other.columns:
            raise ValueError("Maps joined down must have the same number of columns")
        palette = dict(self.palette)
        for key, image in other.palette.items():
            if key in palette:
                original = palette[key]
                if (original.width, original.height) != (image.width, image.height) or (
                    original is not image
                    and original.to_pillow().tobytes() != image.to_pillow().tobytes()
                ):
                    raise ValueError(f"Conflicting images for tile key {key!r}")
                if (key in self.solid) != (key in other.solid) or (
                    (key in self.one_way) != (key in other.one_way)
                ):
                    raise ValueError(f"Conflicting collision settings for tile key {key!r}")
            else:
                palette[key] = image
        rows = (
            [first + second for first, second in zip(self._cells, other._cells)]
            if direction == "right"
            else [*self._cells, *other._cells]
        )
        return TileMap(
            rows,
            palette,
            tile_size=self.tile_size,
            solid=self.solid | other.solid,
            one_way=self.one_way | other.one_way,
            x=self.x,
            y=self.y,
            visible=self.visible,
            layer=self.layer,
            opacity=self.opacity,
            parallax=self.parallax,
            parallax_origin=self.parallax_origin,
        )

    def extend(
        self,
        rows: TileRows,
        *,
        direction: Literal["right", "down"] = "down",
        empty: str = ".",
    ) -> TileMap:
        """Return a new map by adding rows below or to the right.

        Down requires equal column counts; right requires equal row counts.
        Use strings with '.' for empty cells, or explicit tile-key rows with
        None. The optional empty character changes the marker for string rows.
        Unknown keys raise KeyError; empty, uneven or mismatched rows and
        invalid directions raise ValueError. Position, drawing settings, palette
        and collision rules are preserved. The original remains unchanged.
        Example: taller = level.extend(["...", "###"]).
        """
        if rows and all(isinstance(row, str) for row in rows):
            if not isinstance(empty, str) or len(empty) != 1:
                raise ValueError("empty must be one character")
            rows = [
                [None if key == empty else key for key in row] for row in cast(Sequence[str], rows)
            ]
            empty = "."
        section = TileMap(
            rows,
            self.palette,
            tile_size=self.tile_size,
            solid=self.solid,
            one_way=self.one_way,
            empty=empty,
        )
        return self.join(section, direction=direction)

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
        """Return overlapping cells; solid_only includes solid and one-way keys.

        This is geometric overlap, not directional physical contact. Row-major
        order is stable; edge-only contact is not an overlap.
        """
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
            and (not solid_only or key in self.solid or key in self.one_way)
        )


class TiledBackground:
    """Repeat an image endlessly, with optional camera-relative scrolling.

    area=None fills the viewport; an explicit area stays in stage coordinates.
    parallax=(0, 0) stays fixed on screen (default); (1, 1) scrolls with the
    world. Smaller positive factors suggest distant scenery. Offset adds a
    logical-pixel shift, with positive y upward. Factors must be finite and
    nonnegative; invalid values raise ValueError before changing the pattern.

    Example: TiledBackground("mountains.png", parallax=(0.2, 0)).
    """

    __slots__ = ("_area", "_image", "_layer", "_offset", "_parallax", "_visible")

    def __init__(
        self,
        source: ImageSource,
        *,
        area: Bounds | None = None,
        offset: Point = (0, 0),
        parallax: Point = (0, 0),
        visible: bool = True,
        layer: int = -100,
    ) -> None:
        self._image = _image(source)
        self._area = area
        self._offset = _point(offset, "offset")
        self.parallax = parallax
        self._visible = visible
        self._layer = _integer(layer, "layer")

    @property
    def image(self) -> Image:
        """The immutable repeated image."""
        return self._image

    @image.setter
    def image(self, value: ImageSource) -> None:
        self._image = _image(value)

    @property
    @deprecated("costume is deprecated; use image")
    def costume(self) -> Image:
        """Deprecated alias for image; reads the same current visual."""
        return self.image

    @costume.setter
    @deprecated("costume is deprecated; use image")
    def costume(self, value: ImageSource) -> None:
        self.image = value

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
    def parallax(self) -> Point:
        """Nonnegative camera factors: 0 stays on screen; 1 scrolls with the world.

        Each axis is independent. Offset remains an additional pattern shift.
        Assignment validates both finite factors before changing this setting.
        """
        return self._parallax

    @parallax.setter
    def parallax(self, value: Point) -> None:
        x, y = _point(value, "parallax")
        if x < 0 or y < 0:
            raise ValueError("Parallax must be nonnegative")
        self._parallax = (x, y)

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
