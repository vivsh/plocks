"""Concrete Pymunk construction, fixed stepping and local contact queries."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, degrees, hypot, inf, isfinite, radians
from typing import TYPE_CHECKING

from .errors import PhysicsError
from .geometry import Point, _Placement, _point, _positive
from .physics import Body, BodyType, Box, Circle, Physics, _native

if TYPE_CHECKING:
    import pymunk

    from ._commands import Actor
    from ._operations import _Request
    from .stage import Stage
    from .tiling import TileMap


_ONE_WAY = 1


@dataclass(slots=True)
class _TileBody:
    tilemap: TileMap
    native: pymunk.Body | None


def _space(world: Physics) -> pymunk.Space:
    if world._space is None:
        raise PhysicsError("This physics world is closed")
    return world._space


def _moment(shape: Box | Circle, scale: float, mass: float) -> float:
    import pymunk

    value = (
        pymunk.moment_for_box(mass, (shape.width * scale, shape.height * scale))
        if isinstance(shape, Box)
        else pymunk.moment_for_circle(mass, 0, shape.radius * scale)
    )
    return _positive(float(value), "scaled inertia")


def _one_way(actor: Actor) -> bool:
    """Borrow immutable platform configuration; Puppets remain ordinary colliders."""
    from .sprites import Sprite

    return isinstance(actor, Sprite) and actor.one_way


def _begin_one_way(arbiter: pymunk.Arbiter, space: pymunk.Space, data: object) -> bool:
    """Reject underside/side pairs until separation; let the solver handle relative velocity.

    Rejecting a separating top contact would latch an ignored pair when a lift
    starts descending, preventing the rider from catching up and landing again.
    """
    return bool(arbiter.normal.y > 0.5)


def _shape(
    native: pymunk.Body, definition: Box | Circle, scale: float, *, one_way: bool = False
) -> pymunk.Shape:
    import pymunk

    x, y = _point((definition.center[0] * scale, definition.center[1] * scale), "scaled center")
    if isinstance(definition, Circle):
        if one_way:
            raise PhysicsError("One-way platforms require a Box collision shape")
        return pymunk.Circle(native, _positive(definition.radius * scale, "scaled radius"), (x, y))
    w, h = (
        _positive(definition.width * scale, "scaled width") / 2,
        _positive(definition.height * scale, "scaled height") / 2,
    )
    if one_way:
        edge = pymunk.Segment(native, (x - w, y + h), (x + w, y + h), 0)
        edge.collision_type = _ONE_WAY
        return edge
    return pymunk.Poly(native, [(x - w, y - h), (x + w, y - h), (x + w, y + h), (x - w, y + h)])


def _default_shape(actor: Actor) -> Box:
    from .geometry import _rotate
    from .rigging import _pivots
    from .sprites import Sprite

    points: list[Point] = []
    if isinstance(actor, Sprite):
        image = actor.image
        ax, ay = image.anchor
        points = [(x - ax, ay - y) for x in (0, image.width) for y in (0, image.height)]
    else:
        pivots = _pivots(actor.pose)
        for name, image in actor.parts.items():
            (px, py), angle = pivots[name]
            ax, ay = image.anchor
            for x in (0, image.width):
                for y in (0, image.height):
                    rx, ry = _rotate((x - ax, ay - y), 90 + angle)
                    points.append((px + rx, py + ry))
    left, right = min(x for x, _ in points), max(x for x, _ in points)
    bottom, top = min(y for _, y in points), max(y for _, y in points)
    return Box(right - left, top - bottom, ((left + right) / 2, (bottom + top) / 2))


def _attach(world: Physics, actor: Actor) -> None:
    import pymunk

    role = actor.body_type
    if role is BodyType.NONE:
        return
    definition = _default_shape(actor)
    native_type = {
        BodyType.DYNAMIC: pymunk.Body.DYNAMIC,
        BodyType.STATIC: pymunk.Body.STATIC,
        BodyType.KINEMATIC: pymunk.Body.KINEMATIC,
    }[role]
    native = pymunk.Body(1, _moment(definition, actor.scale, 1), body_type=native_type)
    native.position = actor.position
    native.angle = radians(90 - actor.direction)
    native.center_of_gravity = (
        definition.center[0] * actor.scale,
        definition.center[1] * actor.scale,
    )
    shape = _shape(native, definition, actor.scale, one_way=_one_way(actor))
    shape.friction, shape.elasticity = 0.7, 0
    _space(world).add(native, shape)
    body = object.__new__(Body)
    body._actor, body._world, body._native, body._shape = actor, world, native, definition
    body._drag = (0, 0)
    world._bodies.append(body)
    actor._transform = body


def _replace_shape(body: Body, definition: Box | Circle, scale: float) -> None:
    native = _native(body)
    moment = (
        inf
        if body.rotation_locked or body.body_type is not BodyType.DYNAMIC
        else _moment(definition, scale, native.mass)
    )
    from ._connections import _anchor_changes, _apply_anchors

    changes = _anchor_changes(body, scale)
    friction, bounce, sensor = body.friction, body.bounce, body.sensor
    replacement = _shape(native, definition, scale, one_way=_one_way(body._actor))
    replacement.friction, replacement.elasticity = friction, bounce
    replacement.sensor = sensor
    space = _space(body._world)
    previous = tuple(native.shapes)
    previous = tuple(
        shape for shape in previous if shape is not replacement and shape.space is space
    )
    space.add(replacement)
    try:
        _apply_anchors(changes)
        space.remove(*previous)
    except BaseException as error:
        try:
            _apply_anchors(changes, restore=True)
        except BaseException as cleanup:  # noqa: BLE001 -- restore geometry without masking failure
            error.add_note(f"Anchor rollback also failed: {cleanup!r}")
        try:
            if replacement.space is space:
                space.remove(replacement)
            replacement.body = None
            for shape in previous:
                if shape.space is None:
                    space.add(shape)
        except BaseException as cleanup:  # noqa: BLE001 -- retain primary replacement failure
            error.add_note(f"Shape rollback also failed: {cleanup!r}")
        raise
    for shape in previous:
        shape.body = None
    native.center_of_gravity = (definition.center[0] * scale, definition.center[1] * scale)
    native.moment = moment
    body._shape = definition
    space.reindex_shapes_for_body(native)
    native.activate()


def _retire(body: Body) -> None:
    if body._native is None:
        return
    native = body._native
    actor = body._actor
    from ._connections import _remove_actor

    _remove_actor(body._world, actor)
    placement = _Placement(
        (float(native.position.x), float(native.position.y)),
        (90 - degrees(native.angle)) % 360,
        body.body_type,
    )
    space = _space(body._world)
    shapes = tuple(shape for shape in native.shapes if shape.space is space)
    space.remove(*shapes, native)
    for shape in tuple(native.shapes):
        shape.body = None
    body._native = None
    body._world._bodies.remove(body)
    if actor._transform is body:
        actor._transform = placement


def _close(world: Physics) -> None:
    if world._space is None:
        return
    for link in tuple(world._connections):
        link.disconnect()
    for body in tuple(world._bodies):
        _retire(body)
    for terrain in tuple(world._terrain):
        _remove_terrain(world, terrain.tilemap)
    world._space = None


def _contacts(body: Body) -> list[tuple[pymunk.Body, Point, Point]]:
    native = _native(body)
    contacts: list[tuple[pymunk.Body, Point, Point]] = []

    def collect(arbiter: pymunk.Arbiter) -> None:
        a, b = arbiter.shapes
        mine, other = (a, b) if a.body is native else (b, a)
        if mine.sensor or other.sensor:
            return
        fresh = mine.shapes_collide(other)
        if not fresh.points:
            return
        normal = fresh.normal
        # Pymunk 6.11 shapes_collide can flip Segment/Poly normals without
        # flipping distance. Derive signed separation from the fresh geometry.
        if min((p.point_b - p.point_a).dot(normal) for p in fresh.points) > 0.2:
            return
        # shapes_collide normal points from mine toward the other surface.
        support = (-float(normal.x), -float(normal.y))
        point = fresh.points[0].point_a
        if other.body is not None:
            contacts.append((other.body, support, (float(point.x), float(point.y))))

    native.each_arbiter(collect)
    return contacts


def _grounded(body: Body) -> bool:
    native = _native(body)
    gx, gy = body._world.gravity
    magnitude = hypot(gx, gy)
    if not magnitude:
        return False
    for other, (nx, ny), point in _contacts(body):
        relative = native.velocity_at_world_point(point) - other.velocity_at_world_point(point)
        if (
            nx * (-gx / magnitude) + ny * (-gy / magnitude) > 0.5
            and relative.x * nx + relative.y * ny <= 1
        ):
            return True
    return False


def _touching(body: Body, other: Body | TileMap) -> bool:
    target = (
        _native(other)
        if isinstance(other, Body)
        else next((t.native for t in body._world._terrain if t.tilemap is other), None)
    )
    return target is not None and any(native is target for native, _, _ in _contacts(body))


def _remove_terrain(world: Physics, tilemap: TileMap) -> None:
    for terrain in tuple(world._terrain):
        if terrain.tilemap is tilemap:
            if terrain.native is not None:
                shapes = tuple(terrain.native.shapes)
                _space(world).remove(*shapes, terrain.native)
                for shape in shapes:
                    shape.body = None
                terrain.native = None
            world._terrain.remove(terrain)


def _terrain(
    world: Physics,
    tilemap: TileMap,
    *,
    cells: list[list[str | None]] | None = None,
    position: Point | None = None,
) -> None:
    import pymunk

    rows = tilemap._cells if cells is None else cells
    collidable = tilemap.solid | tilemap.one_way
    count = sum(key in collidable for row in rows for key in row)
    count += sum(
        len(t.native.shapes)
        for t in world._terrain
        if t.tilemap is not tilemap and t.native is not None
    )
    if count > 4096:
        raise PhysicsError("A stage supports at most 4096 collidable tile cells")
    native = pymunk.Body(body_type=pymunk.Body.STATIC)
    native.position = (tilemap.x, tilemap.y) if position is None else position
    w, h = tilemap.tile_size
    shapes: list[pymunk.Shape] = []
    for row, line in enumerate(rows):
        for col, key in enumerate(line):
            if key not in collidable:
                continue
            shape: pymunk.Shape
            if key in tilemap.one_way:
                shape = pymunk.Segment(native, (col * w, -row * h), ((col + 1) * w, -row * h), 0)
                shape.collision_type = _ONE_WAY
                # Only actual neighbors suppress an internal seam; gaps keep their edges.
                before = col - 1 if col and line[col - 1] in tilemap.one_way else col
                after = (
                    col + 2 if col + 1 < len(line) and line[col + 1] in tilemap.one_way else col + 1
                )
                shape.set_neighbors((before * w, -row * h), (after * w, -row * h))
            else:
                shape = pymunk.Poly(
                    native,
                    [
                        (col * w, -row * h),
                        ((col + 1) * w, -row * h),
                        ((col + 1) * w, -(row + 1) * h),
                        (col * w, -(row + 1) * h),
                    ],
                )
            shape.friction = 0.7
            shapes.append(shape)
    _space(world).add(native, *shapes)
    _remove_terrain(world, tilemap)
    world._terrain.append(_TileBody(tilemap, native))


def _travel_speed(body: Body, dt: float, requests: tuple[_Request | None, ...]) -> float:
    """Conservatively include linear/angular travel and currently applied acceleration."""
    from ._operations import _ForceRun, _TorqueRun

    native = _native(body)
    definition = body.shape
    radius = (
        hypot(definition.width, definition.height) / 2
        if isinstance(definition, Box)
        else definition.radius
    ) * body._actor.scale
    speed = hypot(*native.velocity) + abs(float(native.angular_velocity)) * radius
    if body.body_type is not BodyType.DYNAMIC:
        return speed
    force = hypot(*native.force)
    torque = abs(float(native.torque))
    for request in requests:
        if isinstance(request, _ForceRun) and request.body is body:
            magnitude = hypot(*request.vector)
            force += magnitude
            if request.point is not None:
                center = native.local_to_world(native.center_of_gravity)
                torque += magnitude * (
                    hypot(request.point[0] - center.x, request.point[1] - center.y) + speed * dt
                )
        elif isinstance(request, _TorqueRun) and request.body is body:
            torque += abs(request.amount)
    acceleration = hypot(*body._world.gravity) + force / float(native.mass)
    acceleration += torque / float(native.moment) * radius
    return speed + acceleration * dt


def _substeps(world: Physics, dt: float, requests: tuple[_Request | None, ...]) -> int:
    """Keep relative travel below a quarter of the smallest moving collider dimension.

    Derive the count locally in worlds with one-way platforms or connections. Retain the
    usual four substeps for ordinary scenes; reject an unsafe count rather than
    capping it silently or allowing an unbounded native stepping loop.
    """
    from ._connections import _steps as connection_steps

    base = connection_steps(world, dt)
    if (
        not world._connections
        and not any(t.tilemap.one_way for t in world._terrain)
        and not any(_one_way(body._actor) for body in world._bodies)
    ):
        return 4
    extent, speed = inf, 0.0
    for body in world._bodies:
        if body.body_type is BodyType.STATIC:
            continue
        speed = max(speed, _travel_speed(body, dt, requests))
        if body.body_type is BodyType.DYNAMIC:
            shape = body.shape
            size = min(shape.width, shape.height) if isinstance(shape, Box) else 2 * shape.radius
            extent = min(extent, size * body._actor.scale)
    if extent == inf:
        return base
    required = dt * (2 * speed) / (extent / 4)
    if not isfinite(required) or required > 1024:
        raise PhysicsError(
            "Physical motion requires more than 1024 physics substeps; "
            "reduce speed/force, enlarge the collider, or increase Stage(tick_rate=...)."
        )
    return max(base, ceil(required))


def _integrate(stage: Stage, dt: float) -> None:
    from ._operations import _ForceRun, _Glide, _TorqueRun
    from ._scripts import _fibers
    from .motion import _ease

    world = stage._physics
    if world is None:
        return
    requests = tuple(f.waiting for root in tuple(stage._actions) for f in _fibers(root))
    for request in requests:
        if not isinstance(request, _Glide) or not isinstance(request.actor._transform, Body):
            continue
        native = _native(request.actor._transform)
        t = (
            1
            if not request.seconds
            else min(1, max(0, (stage.time + dt - request.started) / request.seconds))
        )
        t = _ease(t, request.easing)
        vx, vy = native.velocity
        if request.x is not None:
            start, end = request.x
            vx = ((1 - t) * start + t * end - request.actor.x) / dt
        if request.y is not None:
            start, end = request.y
            vy = ((1 - t) * start + t * end - request.actor.y) / dt
        native.velocity = (vx, vy)
    # Adapt native precision without changing the simulation clock or action deadlines.
    count = _substeps(world, dt, requests)
    substep = dt / count
    for index in range(count):
        start = stage.time + index * substep
        for request in requests:
            if not isinstance(request, (_ForceRun, _TorqueRun)):
                continue
            weight = (
                max(
                    0,
                    min(start + substep, request.started + request.seconds)
                    - max(start, request.started),
                )
                / substep
            )
            if not weight:
                continue
            native = _native(request.body)
            if isinstance(request, _ForceRun):
                point = (
                    native.local_to_world(native.center_of_gravity)
                    if request.point is None
                    else request.point
                )
                native.apply_force_at_world_point(
                    (request.vector[0] * weight, request.vector[1] * weight), point
                )
            else:
                native.torque -= request.amount * weight
        for body in world._bodies:
            if body._drag == (0, 0) or body.body_type is not BodyType.DYNAMIC:
                continue
            native = _native(body)
            vx, vy = native.velocity
            dx, dy = body._drag
            native.velocity = (
                max(0, vx - dx * substep) if vx > 0 else min(0, vx + dx * substep),
                max(0, vy - dy * substep) if vy > 0 else min(0, vy + dy * substep),
            )
        _space(world).step(substep)
        if world._connections:
            for body in world._bodies:
                native = _native(body)
                if not all(
                    isfinite(v)
                    for v in (
                        *native.position,
                        *native.velocity,
                        native.angle,
                        native.angular_velocity,
                    )
                ):
                    raise PhysicsError(
                        "Physical connection motion became nonfinite; reduce the workload"
                    )
