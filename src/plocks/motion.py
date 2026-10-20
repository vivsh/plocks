"""Direction, visual rotation styles, and simulation easing."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from .geometry import Bounds, Point, _rotate

if TYPE_CHECKING:
    from .physics import Body
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
    image = actor.image
    ax, ay = image.anchor
    points: list[Point] = []
    for x in (0, image.width):
        for y in (0, image.height):
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
            _move_to(actor, actor.x + x if x else None, actor.y + y if y else None)
        return True
    return False


def _move(actor: Sprite | Puppet, steps: float) -> None:
    dx, dy = _rotate((steps, 0), actor.direction)
    _move_to(actor, actor.x + dx, actor.y + dy)


def _move_to(actor: Sprite | Puppet, x: float | None, y: float | None) -> None:
    from ._scripts import _conflicts
    from .geometry import _number

    px = actor.x if x is None else _number(x, "x")
    py = actor.y if y is None else _number(y, "y")
    _conflicts(actor, x is not None, y is not None)
    _set_position(actor, (px, py))


def _point_towards(actor: Sprite | Puppet, target: Point | Sprite | Puppet) -> None:
    from math import atan2, degrees

    from .geometry import _point

    point = _point(target) if isinstance(target, tuple) else target.position
    dx, dy = point[0] - actor.x, point[1] - actor.y
    if dx or dy:
        actor.direction = degrees(atan2(dx, dy))


def _random(actor: Sprite | Puppet, bounds: Bounds | None) -> None:
    from random import uniform

    area = _area(actor, bounds)
    actor.position = uniform(area.left, area.right), uniform(area.bottom, area.top)


def _body_position(body: Body) -> Point:
    from .physics import _native

    value = _native(body).position
    return float(value.x), float(value.y)


def _body_direction(body: Body) -> float:
    from math import degrees

    from .physics import _native

    return (90 - degrees(_native(body).angle)) % 360


def _set_position(actor: Sprite | Puppet, position: Point) -> None:
    from ._physics import _ONE_WAY, _one_way, _space
    from .geometry import _Placement
    from .physics import Body, _native

    if isinstance(actor._transform, Body):
        native = _native(actor._transform)
        space = _space(actor._transform._world)
        vertical_teleport = abs(native.position.y - position[1]) > 1e-9
        native.position = position
        space.reindex_shapes_for_body(native)
        if vertical_teleport and (
            _one_way(actor)
            or any(
                hit.shape is not None and hit.shape.collision_type == _ONE_WAY
                for shape in native.shapes
                for hit in space.shape_query(shape)
            )
        ):
            # Respawning onto a platform must not inherit an earlier rejected pair.
            # Reinsert these same native shapes; no contact history is retained here.
            shapes = tuple(native.shapes)
            space.remove(*shapes)
            space.add(*shapes)
        native.activate()
    else:
        actor._transform = _Placement(position, actor.direction, actor.body_type)


def _set_direction(actor: Sprite | Puppet, direction: float) -> None:
    from math import radians

    from ._physics import _one_way
    from .errors import PhysicsError

    if _one_way(actor) and direction % 360 != 90:
        raise PhysicsError("One-way platforms must stay horizontal (direction=90)")

    from ._physics import _space
    from .geometry import _Placement
    from .physics import Body, _native

    if isinstance(actor._transform, Body):
        native = _native(actor._transform)
        native.angle = radians(90 - direction)
        _space(actor._transform._world).reindex_shapes_for_body(native)
        native.activate()
    else:
        actor._transform = _Placement(actor.position, direction, actor.body_type)
