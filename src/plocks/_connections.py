"""Validate, attach and retire native connection resources without copied state."""

from __future__ import annotations

from math import ceil, hypot, isfinite, radians, sqrt
from typing import TYPE_CHECKING

from .connections import Connection, Hinge, Motor, Rope, Spring
from .errors import PhysicsError
from .geometry import Point, _number, _point, _positive

if TYPE_CHECKING:
    import pymunk
    from pymunk import constraints

    from ._commands import Actor
    from .physics import Body, Physics

    type _Anchored = constraints.SlideJoint | constraints.PivotJoint | constraints.DampedSpring
    type _AnchorChange = tuple[_Anchored, bool, Point, Point]


def _require(link: Connection) -> tuple[constraints.Constraint, ...]:
    if not link.connected or link._world._space is None:
        raise PhysicsError("This connection was disconnected; create a new connection")
    return link._native


def _endpoint(
    world: Physics, value: Actor | Point, anchor: Point
) -> tuple[pymunk.Body, Point, Actor | Point]:
    from ._physics import _space
    from .physics import _native
    from .puppets import Puppet
    from .sprites import Sprite

    point = _point(anchor, "anchor")
    if isinstance(value, (Sprite, Puppet)):
        if value._stage is not world._stage:
            raise PhysicsError("Connection actors must belong to this stage")
        body = _native(value.body)
        return (
            body,
            _point((point[0] * value.scale, point[1] * value.scale), "scaled anchor"),
            value,
        )
    if not isinstance(value, tuple) or len(value) != 2:
        raise TypeError("Connection endpoints are actors or world-coordinate Points")
    fixed = _point(value, "world anchor")
    if point != (0, 0):
        raise ValueError("A fixed world endpoint cannot also have a local anchor")
    static = _space(world).static_body
    local = static.world_to_local(fixed)
    return static, (float(local.x), float(local.y)), fixed


def _ends(
    world: Physics, a: Actor | Point, b: Actor | Point, anchor_a: Point, anchor_b: Point
) -> tuple[pymunk.Body, pymunk.Body, Point, Point, tuple[Actor | Point, Actor | Point]]:
    from ._physics import _space

    if world._stage._state == "closed":
        raise PhysicsError("This physics world is closed")
    _space(world)
    first, pa, ea = _endpoint(world, a, anchor_a)
    second, pb, eb = _endpoint(world, b, anchor_b)
    if first is second:
        raise PhysicsError("A connection requires two distinct bodies")
    if first.body_type != 0 and second.body_type != 0:
        raise PhysicsError("A connection needs at least one dynamic physical actor")
    return first, second, pa, pb, (ea, eb)


def _budget(world: Physics, count: int) -> None:
    if sum(len(link._native) for link in world._connections) + count > 1024:
        raise PhysicsError("A world supports at most 1024 native connection constraints")


def _attach[C: Connection](
    world: Physics,
    link: C,
    endpoints: tuple[Actor | Point, Actor | Point],
    natives: tuple[constraints.Constraint, ...],
    collide: bool,
) -> C:
    """Publish only after native attachment; roll back partial allocation on failure."""
    from ._physics import _space

    if not isinstance(collide, bool):
        raise TypeError("collide must be bool")
    _budget(world, len(natives))
    space = _space(world)
    link._world, link._endpoints, link._native = world, endpoints, natives
    try:
        for native in natives:
            native.collide_bodies = collide
        space.add(*natives)
        world._connections.append(link)
    except BaseException as error:
        for native in reversed(natives):
            try:
                if native in space.constraints:
                    space.remove(native)
            except BaseException as cleanup:  # noqa: BLE001 -- preserve admission failure during rollback
                error.add_note(f"Connection cleanup also failed: {cleanup!r}")
        link._native = ()
        raise
    return link


def _rope(
    world: Physics,
    a: Actor | Point,
    b: Actor | Point,
    *,
    length: float | None,
    anchor_a: Point,
    anchor_b: Point,
    collide: bool,
) -> Rope:
    from pymunk import constraints

    first, second, pa, pb, endpoints = _ends(world, a, b, anchor_a, anchor_b)
    p, q = first.local_to_world(pa), second.local_to_world(pb)
    maximum = _positive(hypot(q.x - p.x, q.y - p.y) if length is None else length, "length")
    _options(world, 1, collide)
    native = constraints.SlideJoint(first, second, pa, pb, 0, maximum)
    return _attach(world, object.__new__(Rope), endpoints, (native,), collide)


def _disconnect(link: Connection) -> None:
    if not link.connected:
        return
    if isinstance(link, Hinge):
        for child in tuple(link._world._connections):
            if isinstance(child, Motor) and child._hinge is link:
                _disconnect(child)
    space = link._world._space
    if space is not None:
        for native in reversed(link._native):
            if native in space.constraints:
                space.remove(native)
    link._native = ()
    if link in link._world._connections:
        link._world._connections.remove(link)


def _remove_actor(world: Physics, actor: Actor) -> None:
    for link in tuple(world._connections):
        if any(endpoint is actor for endpoint in link._endpoints):
            _disconnect(link)


def _anchors(link: Rope | Hinge | Spring) -> tuple[Point, Point]:
    from pymunk import constraints

    native = _require(link)[0]
    assert isinstance(
        native, (constraints.SlideJoint, constraints.PivotJoint, constraints.DampedSpring)
    )
    a, b = native.a.local_to_world(native.anchor_a), native.b.local_to_world(native.anchor_b)
    return (float(a.x), float(a.y)), (float(b.x), float(b.y))


def _options(world: Physics, count: int, collide: bool) -> None:
    if not isinstance(collide, bool):
        raise TypeError("collide must be bool")
    _budget(world, count)


def _hinge(
    world: Physics,
    a: Actor | Point,
    b: Actor | Point,
    *,
    anchor_a: Point,
    anchor_b: Point,
    limits: tuple[float, float] | None,
    collide: bool,
) -> Hinge:
    from pymunk import constraints

    first, second, pa, pb, endpoints = _ends(world, a, b, anchor_a, anchor_b)
    angle_range: tuple[float, float] | None = None
    if limits is not None:
        low, high = _point(limits, "limits")
        if not low <= 0 <= high:
            raise ValueError("Hinge limits must be ordered and include zero")
        rest = second.angle - first.angle
        angle_range = (
            _number(rest - radians(high), "minimum angle"),
            _number(rest - radians(low), "maximum angle"),
        )
    _options(world, 1 if angle_range is None else 2, collide)
    pivot = constraints.PivotJoint(first, second, pa, pb)
    natives: tuple[constraints.Constraint, ...] = (pivot,)
    if angle_range is not None:
        natives += (constraints.RotaryLimitJoint(first, second, *angle_range),)
    return _attach(world, object.__new__(Hinge), endpoints, natives, collide)


def _spring(
    world: Physics,
    a: Actor | Point,
    b: Actor | Point,
    *,
    rest_length: float | None,
    stiffness: float,
    damping: float,
    anchor_a: Point,
    anchor_b: Point,
    collide: bool,
) -> Spring:
    from pymunk import constraints

    first, second, pa, pb, endpoints = _ends(world, a, b, anchor_a, anchor_b)
    p, q = first.local_to_world(pa), second.local_to_world(pb)
    length = _positive(
        hypot(q.x - p.x, q.y - p.y) if rest_length is None else rest_length, "rest_length"
    )
    k, d = _positive(stiffness, "stiffness"), _number(damping, "damping", minimum=0)
    _options(world, 1, collide)
    native = constraints.DampedSpring(first, second, pa, pb, length, k, d)
    return _attach(world, object.__new__(Spring), endpoints, (native,), collide)


def _can_rotate(a: pymunk.Body, b: pymunk.Body) -> bool:
    return any(body.body_type == 0 and isfinite(body.moment) and body.moment > 0 for body in (a, b))


def _motor(hinge: Hinge, *, speed: float, max_torque: float) -> Motor:
    from pymunk import constraints

    native = _require(hinge)[0]
    rate, torque = radians(_number(speed, "speed")), _positive(max_torque, "max_torque")
    if any(isinstance(link, Motor) and link._hinge is hinge for link in hinge._world._connections):
        raise PhysicsError("A hinge already has a connected motor")
    if not _can_rotate(native.a, native.b):
        raise PhysicsError("A motor requires an unlocked dynamic rotational body")
    _budget(hinge._world, 1)
    drive = constraints.SimpleMotor(native.a, native.b, rate)
    drive.max_force = torque
    link = object.__new__(Motor)
    link._hinge = hinge
    return _attach(hinge._world, link, hinge._endpoints, (drive,), True)


def _check_rotation(body: Body, locked: bool) -> None:
    """Reject locking the last rotational endpoint of a live motor before mutation."""
    if not locked:
        return
    from .physics import _native

    native = _native(body)
    for link in body._world._connections:
        if not isinstance(link, Motor):
            continue
        drive = _require(link)[0]
        if native is drive.a or native is drive.b:
            other = drive.b if native is drive.a else drive.a
            if other.body_type != 0 or not isfinite(other.moment) or other.moment <= 0:
                raise PhysicsError("Disconnect the motor before locking its last rotational body")


def _anchor_changes(body: Body, scale: float) -> list[_AnchorChange]:
    """Capture old/new local anchors locally for a shape/scale replacement."""
    from pymunk import constraints

    changes: list[_AnchorChange] = []
    ratio = _number(scale / body._actor.scale, "anchor scale ratio")
    if ratio == 1:
        return changes
    for link in body._world._connections:
        for index, endpoint in enumerate(link._endpoints):
            if endpoint is not body._actor:
                continue
            for native in link._native:
                if not isinstance(
                    native,
                    (constraints.SlideJoint, constraints.PivotJoint, constraints.DampedSpring),
                ):
                    continue
                old = native.anchor_a if index == 0 else native.anchor_b
                value = _point((old.x * ratio, old.y * ratio), "scaled anchor")
                changes.append((native, index == 0, (float(old.x), float(old.y)), value))
    return changes


def _apply_anchors(changes: list[_AnchorChange], *, restore: bool = False) -> None:
    for native, first, before, after in changes:
        value = before if restore else after
        if first:
            native.anchor_a = value
        else:
            native.anchor_b = value
        native.activate_bodies()


def _steps(world: Physics, dt: float) -> int:
    """Bound spring frequency and motor angular travel using only native parameters."""
    from pymunk import constraints

    required = 4.0
    for link in world._connections:
        native = link._native[0]
        if isinstance(native, constraints.DampedSpring):
            inverse_mass = sum(
                1 / body.mass for body in (native.a, native.b) if body.body_type == 0
            )
            frequency_squared = native.stiffness * inverse_mass
            if not isfinite(frequency_squared):
                raise PhysicsError("Spring stiffness/mass exceeds safe physics stepping")
            required = max(required, dt * sqrt(frequency_squared) * 4)
        elif isinstance(native, constraints.SimpleMotor):
            required = max(required, dt * abs(native.rate) * 4)
    if not isfinite(required) or required > 1024:
        raise PhysicsError(
            "Physical connections require more than 1024 substeps; lower stiffness/speed or increase tick_rate"
        )
    return ceil(required)
