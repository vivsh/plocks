"""Immutable spatial query results and typed, query-only collision exclusions."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .geometry import Point

if TYPE_CHECKING:
    from .puppets import Puppet
    from .sprites import Sprite
    from .tiling import TileMap

type CastTarget = Sprite | Puppet | TileMap
"""An actor or tilemap owning physical geometry returned by a cast."""
type CastIgnore = Iterable[CastTarget] | Callable[[CastTarget], bool] | None
"""Objects to skip, or a pure synchronous predicate returning True to skip an owner."""


@dataclass(frozen=True, slots=True)
class CastHit:
    """Nearest cast hit; a caller-owned snapshot, never retained by the engine.

    target is the live owner; other fields are captured world-coordinate values.
    distance is ray/source-anchor travel in pixels. normal points out of the hit
    surface; a ray starting inside uses (0, 0). cell identifies a tile's zero-based
    (row, column), or None for actors. Later edits do not update this snapshot.
    """

    target: CastTarget
    point: Point
    normal: Point
    distance: float
    cell: tuple[int, int] | None
