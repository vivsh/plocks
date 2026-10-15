"""Direction, visual rotation styles, and simulation easing."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from .geometry import Bounds, Point, _rotate

if TYPE_CHECKING:
    from .puppets import Puppet
    from .sprites import Sprite


class Ease(Enum):
    """Interpolation curves: linear, quadratic in, out, and in/out."""

    LINEAR = "linear"
    IN = "in"
    OUT = "out"
    IN_OUT = "in_out"


class RotationStyle(Enum):
    """Appearance follows direction, mirrors left/right, or remains unrotated."""

    ALL_AROUND = "all_around"
    LEFT_RIGHT = "left_right"
    NONE = "none"


def _ease(progress: float, easing: Ease) -> float:
    if easing is Ease.IN:
        return progress * progress
    if easing is Ease.OUT:
        return 1 - (1 - progress) ** 2
    if easing is Ease.IN_OUT:
        return 2 * progress**2 if progress < 0.5 else 1 - 2 * (1 - progress) ** 2
    return progress


def _visual_direction(direction: float, style: RotationStyle) -> float:
    return direction if style is RotationStyle.ALL_AROUND else 90.0


def _mirrored(direction: float, style: RotationStyle) -> bool:
    return style is RotationStyle.LEFT_RIGHT and 180 < direction % 360 < 360


def _area(actor: Sprite | Puppet, bounds: Bounds | None) -> Bounds:
    from .errors import StageError

    if bounds is None:
        if actor._stage is None:
            raise StageError("Supply bounds or add the actor to a stage")
        bounds = actor._stage.world_bounds
    if bounds.width <= 0 or bounds.height <= 0:
        raise ValueError("Bounds must have positive area")
    return bounds


def _actor_bounds(actor: Sprite | Puppet, direction: float) -> Bounds:
    from .puppets import Puppet, _bounds

    if isinstance(actor, Puppet):
        return _bounds(actor, direction)
    costume = actor.costume
    ax, ay = costume.anchor
    points: list[Point] = []
    for x in (0, costume.width):
        for y in (0, costume.height):
            local = (x - ax, ay - y)
            if _mirrored(direction, actor.rotation_style):
                local = (-local[0], local[1])
            points.append(
                _rotate(local, _visual_direction(direction, actor.rotation_style), actor.scale)
            )
    return Bounds(
        actor.x + min(p[0] for p in points),
        actor.y + min(p[1] for p in points),
        actor.x + max(p[0] for p in points),
        actor.y + max(p[1] for p in points),
    )


def _bounce(actor: Sprite | Puppet, bounds: Bounds | None) -> bool:
    area = _area(actor, bounds)
    box = actor.bounds
    dx, dy = _rotate((1, 0), actor.direction)
    horizontal = (box.left <= area.left and dx < 0) or (box.right >= area.right and dx > 0)
    vertical = (box.bottom <= area.bottom and dy < 0) or (box.top >= area.top and dy > 0)
    direction = -actor.direction if horizontal else actor.direction
    if vertical:
        direction = 180 - direction
    proposed = _actor_bounds(actor, direction)
    if proposed.width > area.width or proposed.height > area.height:
        raise ValueError("The actor is too large to fit inside the bounds")
    x = max(area.left - proposed.left, 0) + min(area.right - proposed.right, 0)
    y = max(area.bottom - proposed.bottom, 0) + min(area.top - proposed.top, 0)
    if horizontal or vertical or x or y:
        actor.direction = direction
        if x or y:
            actor.move_to(x=actor.x + x if x else None, y=actor.y + y if y else None)
        return True
    return False
