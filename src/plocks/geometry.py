"""Finite logical-pixel geometry, with positive y pointing upward."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, isfinite, radians, sin

type Point = tuple[float, float]
"""An (x, y) pair, measured in logical pixels unless an API says otherwise."""
type Color = str | tuple[int, int, int] | tuple[int, int, int, int]
"""A named color, RGB tuple, or RGBA tuple; each channel ranges from 0 to 255."""


def _number(value: float, name: str, *, minimum: float | None = None) -> float:
    """Validate finite scalar geometry without retaining derived state."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number")
    result = float(value)
    if not isfinite(result) or (minimum is not None and result < minimum):
        raise ValueError(f"{name} must be finite and at least {minimum}")
    return result


def _positive(value: float, name: str) -> float:
    result = _number(value, name)
    if result <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return result


def _integer(value: int, name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _point(value: Point, name: str = "position") -> Point:
    return (_number(value[0], f"{name}.x"), _number(value[1], f"{name}.y"))


def _rotate(point: Point, direction: float, scale: float = 1.0) -> Point:
    """Transform an upright local point; direction 90 leaves it unrotated."""
    direction %= 360
    if direction == 0:
        cosine, sine = 0.0, 1.0
    elif direction == 90:
        cosine, sine = 1.0, 0.0
    elif direction == 180:
        cosine, sine = 0.0, -1.0
    elif direction == 270:
        cosine, sine = -1.0, 0.0
    else:
        angle = radians(90 - direction)
        cosine, sine = cos(angle), sin(angle)
    x, y = point
    return scale * (x * cosine - y * sine), scale * (x * sine + y * cosine)


@dataclass(frozen=True)
class Bounds:
    """Immutable world bounds. Merely touching edges do not overlap."""

    left: float
    bottom: float
    right: float
    top: float

    def __post_init__(self) -> None:
        for name in ("left", "bottom", "right", "top"):
            _number(getattr(self, name), name)
        if self.right < self.left or self.top < self.bottom:
            raise ValueError("bounds must have ordered left/right and bottom/top")

    @property
    def width(self) -> float:
        """Horizontal extent, in logical pixels."""
        return self.right - self.left

    @property
    def height(self) -> float:
        """Vertical extent, in logical pixels."""
        return self.top - self.bottom

    @property
    def center(self) -> Point:
        """The midpoint of these bounds."""
        return ((self.left + self.right) / 2, (self.bottom + self.top) / 2)

    def intersects(self, other: Bounds) -> bool:
        """Return whether both axes have positive overlap; edges alone are false."""
        return min(self.right, other.right) > max(self.left, other.left) and min(
            self.top, other.top
        ) > max(self.bottom, other.bottom)

    def contains(self, point: Point) -> bool:
        """Return whether a point lies inside or on the boundary."""
        x, y = _point(point)
        return self.left <= x <= self.right and self.bottom <= y <= self.top
