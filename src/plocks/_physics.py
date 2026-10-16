"""Concrete Pymunk construction, fixed stepping and local contact queries."""

from __future__ import annotations

from dataclasses import dataclass
from math import degrees, hypot, inf, radians
from typing import TYPE_CHECKING

from .errors import PhysicsError
from .geometry import Point, _Placement, _point, _positive
from .physics import Body, BodyType, Box, Circle, Physics, _native

if TYPE_CHECKING:
    import pymunk

    from ._commands import Actor
    from .stage import Stage
    from .tiling import TileMap


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


def _shape(native: pymunk.Body, definition: Box | Circle, scale: float) -> pymunk.Shape:
    import pymunk

    x, y = _point((definition.center[0] * scale, definition.center[1] * scale), "scaled center")
    if isinstance(definition, Circle):
        return pymunk.Circle(native, _positive(definition.radius * scale, "scaled radius"), (x, y))
    w, h = (
        _positive(definition.width * scale, "scaled width") / 2,
        _positive(definition.height * scale, "scaled height") / 2,
    )
    return pymunk.Poly(native, [(x - w, y - h), (x + w, y - h), (x + w, y + h), (x - w, y + h)])


def _default_shape(actor: Actor) -> Box:
    from .geometry import _rotate
    from .rigging import _pivots
    from .sprites import Sprite

    points: list[Point] = []
    if isinstance(actor, Sprite):
        costume = actor.costume
        ax, ay = costume.anchor
        points = [(x - ax, ay - y) for x in (0, costume.width) for y in (0, costume.height)]
    else:
        pivots = _pivots(actor.pose)
        for name, costume in actor.parts.items():
            (px, py), angle = pivots[name]
            ax, ay = costume.anchor
            for x in (0, costume.width):
                for y in (0, costume.height):
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
    shape = _shape(native, definition, actor.scale)
    shape.friction, shape.elasticity = 0.7, 0
    _space(world).add(native, shape)
    body = object.__new__(Body)
    body._actor, body._world, body._native, body._shape = actor, world, native, definition
    world._bodies.append(body)
    actor._transform = body


def _replace_shape(body: Body, definition: Box | Circle, scale: float) -> None:
    native = _native(body)
    moment = (
        inf
        if body.rotation_locked or body.body_type is not BodyType.DYNAMIC
        else _moment(definition, scale, native.mass)
    )
    friction, bounce = body.friction, body.bounce
    replacement = _shape(native, definition, scale)
    replacement.friction, replacement.elasticity = friction, bounce
    space = _space(body._world)
    previous = tuple(native.shapes)
    previous = tuple(
        shape for shape in previous if shape is not replacement and shape.space is space
    )
    space.add(replacement)
    try:
        space.remove(*previous)
    except BaseException:
        space.remove(replacement)
        replacement.body = None
        for shape in previous:
            if shape.space is None:
                space.add(shape)
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
        fresh = mine.shapes_collide(other)
        if not fresh.points or min(p.distance for p in fresh.points) > 0.2:
            return
        normal = fresh.normal
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
    count = sum(key in tilemap._solid for row in rows for key in row)
    count += sum(
        len(t.native.shapes)
        for t in world._terrain
        if t.tilemap is not tilemap and t.native is not None
    )
    if count > 4096:
        raise PhysicsError("A stage supports at most 4096 solid tile cells")
    native = pymunk.Body(body_type=pymunk.Body.STATIC)
    native.position = (tilemap.x, tilemap.y) if position is None else position
    w, h = tilemap.tile_size
    shapes: list[pymunk.Shape] = []
    for row, line in enumerate(rows):
        for col, key in enumerate(line):
            if key in tilemap._solid:
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
    # Fixed native substeps improve contact stability without changing the public clock.
    substep = dt / 4
    for index in range(4):
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
        _space(world).step(substep)
