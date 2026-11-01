"""Persistent actor limits; geometry and native ownership lookups stay local."""

from __future__ import annotations

from math import hypot
from typing import TYPE_CHECKING

from .errors import PhysicsError
from .geometry import Bounds, Point, _point, _positive, _rotate
from .physics import Body, Box, Circle, _native

if TYPE_CHECKING:
    import pymunk

    from ._commands import Actor
    from .imaging import Image
    from .motion import RotationStyle
    from .physics import Physics
    from .rigging import Pose
    from .stage import Stage

_BOUNDARY = 2


def _footprint(
    actor: Actor,
    *,
    position: Point | None = None,
    direction: float | None = None,
    scale: float | None = None,
    definition: Box | Circle | None = None,
    image: Image | None = None,
    pose: Pose | None = None,
    style: RotationStyle | None = None,
) -> Bounds:
    """Compute physical geometry when attached, otherwise transformed image corners."""
    from .motion import _mirrored, _visual_direction
    from .rigging import _pivots
    from .sprites import Sprite

    x, y = actor.position if position is None else position
    direction = actor.direction if direction is None else direction
    scale = actor.scale if scale is None else scale
    if definition is not None or isinstance(actor._transform, Body):
        shape = actor.body.shape if definition is None else definition
        cx, cy = _rotate(shape.center, direction, scale)
        if isinstance(shape, Circle):
            half_width = half_height = shape.radius * scale
        else:
            wx, wy = _rotate((shape.width / 2, 0), direction, scale)
            hx, hy = _rotate((0, shape.height / 2), direction, scale)
            half_width, half_height = abs(wx) + abs(hx), abs(wy) + abs(hy)
        return Bounds(
            x + cx - half_width, y + cy - half_height, x + cx + half_width, y + cy + half_height
        )
    else:
        style = actor.rotation_style if style is None else style
        points_list: list[Point] = []
        parts: tuple[tuple[Point, float, Image], ...]
        if isinstance(actor, Sprite):
            parts = (((0.0, 0.0), 0.0, actor.image if image is None else image),)
        else:
            pivots = _pivots(actor.pose if pose is None else pose)
            parts = tuple((*pivots[name], part) for name, part in actor.parts.items())
        for (px, py), angle, part in parts:
            ax, ay = part.anchor
            for cx in (0, part.width):
                for cy in (0, part.height):
                    rx, ry = _rotate((cx - ax, ay - cy), 90 + angle)
                    local = (px + rx, py + ry)
                    if _mirrored(direction, style):
                        local = (-local[0], local[1])
                    points_list.append(
                        _point(_rotate(local, _visual_direction(direction, style), scale))
                    )
        points = tuple(points_list)
    return Bounds(
        x + min(p[0] for p in points),
        y + min(p[1] for p in points),
        x + max(p[0] for p in points),
        y + max(p[1] for p in points),
    )


def _clip(area: Bounds, footprint: Bounds, position: Point) -> Point:
    """Clip an anchor using its local footprint, avoiding large-position cancellation."""
    if footprint.width > area.width + 1e-8 or footprint.height > area.height + 1e-8:
        raise ValueError("The actor is too large to keep inside these bounds")
    return _point(
        (
            max(area.left - footprint.left, min(position[0], area.right - footprint.right)),
            max(area.bottom - footprint.bottom, min(position[1], area.top - footprint.top)),
        ),
        "contained position",
    )


def _position(actor: Actor, position: Point) -> Point:
    """Limit a normal position write without canceling its active action."""
    area = actor._movement_bounds
    return position if area is None else _clip(area, _footprint(actor, position=(0, 0)), position)


def _changed(
    actor: Actor,
    *,
    direction: float | None = None,
    scale: float | None = None,
    definition: Box | Circle | None = None,
    image: Image | None = None,
    pose: Pose | None = None,
    style: RotationStyle | None = None,
) -> Point:
    """Validate prospective geometry before its author commits a mutation."""
    if actor._movement_bounds is None:
        return actor.position
    result = _clip(
        actor._movement_bounds,
        _footprint(
            actor,
            position=(0, 0),
            direction=direction,
            scale=scale,
            definition=definition,
            image=image,
            pose=pose,
            style=style,
        ),
        actor.position,
    )
    _check_linked(actor, result)
    return result


def _check_linked(actor: Actor, position: Point, *, tolerance: float = 1e-8) -> None:
    """Do not teleport a connected assembly when enabling or changing limits."""
    if not isinstance(actor._transform, Body):
        return
    if hypot(position[0] - actor.x, position[1] - actor.y) <= tolerance:
        return
    if any(actor is end for link in actor.body._world._connections for end in link._endpoints):
        raise PhysicsError(
            "Containment would displace a connected actor; position the assembly inside first"
        )


def _pair(world: Physics, first: pymunk.Body, second: pymunk.Body) -> bool | None:
    """Return owner-only boundary eligibility, or defer ordinary collision rules."""
    for body in world._bodies:
        wall = body._boundary_native
        if wall is not None and (first is wall or second is wall):
            return second is body._native if first is wall else first is body._native
    return None


def _walls(body: Body, area: Bounds) -> pymunk.Body:
    """Acquire one private static body and its four segments transactionally."""
    import pymunk

    from ._physics import _space

    if (
        sum(item._boundary_native is not None for item in body._world._bodies if item is not body)
        >= 1024
    ):
        raise PhysicsError("A stage supports at most 1024 bounded physical actors")
    native = pymunk.Body(body_type=pymunk.Body.STATIC)
    corners = (
        (area.left, area.bottom),
        (area.right, area.bottom),
        (area.right, area.top),
        (area.left, area.top),
    )
    segments = tuple(
        pymunk.Segment(native, start, corners[(i + 1) % 4], 0) for i, start in enumerate(corners)
    )
    for segment in segments:
        segment.collision_type = _BOUNDARY
        segment.friction = segment.elasticity = 0
    space = _space(body._world)
    try:
        space.add(native, *segments)
    except BaseException:
        attached = tuple(shape for shape in segments if shape.space is space)
        if attached:
            space.remove(*attached)
        if native.space is space:
            space.remove(native)
        for shape in segments:
            shape.body = None
        raise
    return native


def _release(body: Body) -> None:
    """Release the attachment's boundary resource; safe to call repeatedly."""
    from ._physics import _space

    wall = body._boundary_native
    if wall is None:
        return
    space = _space(body._world)
    shapes = tuple(wall.shapes)
    space.remove(*shapes, wall)
    for shape in shapes:
        shape.body = None
    body._boundary_native = None


def _clear_velocity(body: Body, box: Bounds, area: Bounds) -> None:
    native = _native(body)
    vx, vy = native.velocity
    if (box.left <= area.left + 1e-8 and vx < 0) or (box.right >= area.right - 1e-8 and vx > 0):
        vx = 0
    if (box.bottom <= area.bottom + 1e-8 and vy < 0) or (box.top >= area.top - 1e-8 and vy > 0):
        vy = 0
    if (vx, vy) != native.velocity:
        native.velocity = vx, vy


def _enforce(actor: Actor, *, stepping: bool = False) -> None:
    """Contain current geometry, retaining solver contacts and inward/tangent speed."""
    area = actor._movement_bounds
    if area is None:
        return
    before = actor.position
    box = _footprint(actor, position=(0, 0))
    position = _clip(area, box, before)
    _check_linked(actor, position, tolerance=0.2 if stepping else 1e-8)
    if position != actor.position:
        from ._physics import _space
        from .geometry import _Placement

        if isinstance(actor._transform, Body):
            native = _native(actor._transform)
            native.position = position
            _space(actor.body._world).reindex_shapes_for_body(native)
        else:
            actor._transform = _Placement(position, actor.direction, actor.body_type)
    if isinstance(actor._transform, Body):
        dx, dy = position
        _clear_velocity(
            actor.body, Bounds(box.left + dx, box.bottom + dy, box.right + dx, box.top + dy), area
        )


def _overlap_check(body: Body, position: Point) -> None:
    """Reject initial correction that introduces or deepens a blocking overlap."""
    import pymunk

    from ._combat import _pair as accepts
    from ._physics import _shape, _space

    if position == body._actor.position or body.sensor:
        return
    from ._casts import _source
    from ._physics import _ONE_WAY
    from ._sweep import _expanded

    native, space = _native(body), _space(body._world)
    probe = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
    probe.angle, probe.position = native.angle, position
    shape = _shape(probe, body.shape, body._actor.scale)
    shape.cache_bb()
    offsets, radius = _source(body.shape, body._actor.direction, body._actor.scale)
    try:
        for other in space.bb_query(shape.bb, pymunk.ShapeFilter()):
            if other.body is None or other.body is native or other.sensor:
                continue
            if not accepts(body._world, native, other.body):
                continue
            if (
                other.collision_type == _ONE_WAY
                and min(s.cache_bb().bottom for s in native.shapes) < other.cache_bb().top - 1e-6
            ):
                continue
            expanded = _expanded(other, offsets, radius)
            try:
                depth = float(expanded.point_query(position).distance)
                previous = float(expanded.point_query(body._actor.position).distance)
                if depth < min(-1e-6, previous - 1e-6):
                    raise PhysicsError("Containment would move the actor into solid geometry")
            finally:
                expanded.body = None
    finally:
        shape.body = None


def _configure(actor: Actor, area: Bounds | None) -> None:
    """Validate and replace the actor's persistent rule and attachment resources."""
    if area is not None and not isinstance(area, Bounds):
        raise TypeError("keep_inside requires Bounds or None")
    if area is not None:
        _positive(area.width, "containment width")
        _positive(area.height, "containment height")
    position = (
        actor.position
        if area is None
        else _clip(area, _footprint(actor, position=(0, 0)), actor.position)
    )
    _check_linked(actor, position)
    body = actor._transform if isinstance(actor._transform, Body) else None
    if body is not None:
        _overlap_check(body, position)
        replacement = None if area is None else _walls(body, area)
        _release(body)
        body._boundary_native = replacement
    actor._movement_bounds = area
    _enforce(actor)


def _sample(stage: Stage) -> None:
    """Enforce new image/pose geometry before edge notifications and presentation."""
    from ._physics import _sync_shapes
    from .puppets import Puppet
    from .sprites import Sprite

    _sync_shapes(stage)
    for actor in tuple(stage._members):
        if isinstance(actor, (Sprite, Puppet)):
            _enforce(actor, stepping=True)
