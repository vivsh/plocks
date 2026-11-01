"""Physical contact episodes; Stage owns only the previous accepted owner pairs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .errors import StageError
from .events import Collision
from .geometry import Point
from .physics import Body, Physics, _native
from .queries import CastTarget

if TYPE_CHECKING:
    import pymunk

    from ._commands import Actor
    from ._scripts import WhenBusy
    from .stage import Stage

_MAX_CONTACTS = 8192


def _supported(platform: pymunk.Shape, actor: pymunk.Shape, slop: float) -> bool:
    """Query-only top eligibility for pairs without a native solver arbiter."""
    top, box = platform.cache_bb().top, actor.cache_bb()
    if platform.body is None or actor.body is None or box.bottom < top - 2 * slop:
        return False
    point = ((box.left + box.right) / 2, top)
    relative = actor.body.velocity_at_world_point(point) - platform.body.velocity_at_world_point(
        point
    )
    return float(relative.y) <= 1


def _allowed(world: Physics, mine: pymunk.Shape, other: pymunk.Shape, native: bool) -> bool:
    """Borrow current filters, linked-pair rules and one-way acceptance."""
    from ._combat import _pair
    from ._physics import _ONE_WAY, _space

    a, b = mine.body, other.body
    if a is None or b is None or a is b or not _pair(world, a, b):
        return False
    for link in world._connections:
        bodies = tuple(
            end._transform._native
            for end in link._endpoints
            if not isinstance(end, tuple) and isinstance(end._transform, Body)
        )
        if not link.collide and a in bodies and b in bodies:
            return False
    if native:
        return True
    slop = float(_space(world).collision_slop)
    return (mine.collision_type != _ONE_WAY or _supported(mine, other, slop)) and (
        other.collision_type != _ONE_WAY or _supported(other, mine, slop)
    )


def _tangent(mine: pymunk.Shape, other: pymunk.Shape) -> tuple[Point, Point] | None:
    """Include exact rounded-shape tangency that native circle queries exclude."""
    from ._sweep import _core, _expanded, _witness
    from .geometry import _point

    assert mine.body is not None
    anchor = float(mine.body.position.x), float(mine.body.position.y)
    core, radius = _core(mine)
    offsets = tuple((x - anchor[0], y - anchor[1]) for x, y in core)
    expanded = _expanded(other, offsets, radius)
    try:
        info = expanded.point_query(anchor)
        if abs(float(info.distance)) > 1e-8:
            return None
        normal = _point((float(info.gradient.x), float(info.gradient.y)), "contact normal")
        return _witness(other, anchor, offsets, normal), normal
    finally:
        expanded.body = None


def _actor_contacts(
    world: Physics,
    actor: Actor,
    owners: dict[pymunk.Body, CastTarget],
    result: dict[tuple[Actor, CastTarget], Collision],
) -> None:
    """Collect one receiver synchronously; never leak a native callback exception."""
    import pymunk

    from ._casts import _cell
    from ._physics import _ONE_WAY, _space
    from .tiling import TileMap

    body = _native(actor.body)
    failures: list[BaseException] = []
    raw: list[tuple[pymunk.Shape, pymunk.Shape, Point, Point]] = []

    def record(
        other: pymunk.Shape, point: tuple[float, float], normal: tuple[float, float]
    ) -> None:
        target = owners.get(other.body) if other.body is not None else None
        if target is None or target is actor:
            return
        cell = _cell(target, other) if isinstance(target, TileMap) else None
        key = actor, target
        old = result.get(key)
        if old is None or (cell or (-1, -1)) < (old.cell or (-1, -1)):
            result[key] = Collision(target, point, normal, cell)
        if len(result) > _MAX_CONTACTS:
            raise StageError("Physical contacts exceeded the 8192-pair limit")

    def collect(arbiter: pymunk.Arbiter) -> None:
        if failures:
            return
        try:
            a, b = arbiter.shapes
            mine, other = (a, b) if a.body is body else (b, a)
            points = arbiter.contact_point_set.points
            if not points:
                return
            point = points[0].point_b if mine is a else points[0].point_a
            sign = -1 if mine is a else 1
            normal = arbiter.normal
            raw.append(
                (
                    mine,
                    other,
                    (float(point.x), float(point.y)),
                    (sign * float(normal.x), sign * float(normal.y)),
                )
            )
        except BaseException as error:  # noqa: BLE001 -- raise outside the native callback boundary
            failures.append(error)
        finally:
            # Native arbiters must never escape their callback, even in a traceback.
            del arbiter

    body.each_arbiter(collect)
    if failures:
        raise failures[0]
    for native_mine, native_other, contact_point, contact_normal in raw:
        if _allowed(world, native_mine, native_other, True):
            record(native_other, contact_point, contact_normal)
    for mine in body.shapes:
        mine.cache_bb()
        for hit in _space(world).shape_query(mine):
            other = hit.shape
            if other is None or not _allowed(world, mine, other, False):
                continue
            contact = hit.contact_point_set
            if not contact.points:
                continue
            point = contact.points[0].point_b
            normal = (-float(contact.normal.x), -float(contact.normal.y))
            if other.collision_type == _ONE_WAY:
                normal = (0.0, 1.0)
            elif mine.collision_type == _ONE_WAY:
                normal = (0.0, -1.0)
            record(other, (float(point.x), float(point.y)), normal)
        # Chipmunk excludes zero-depth circle tangency from shape_query. Use the
        # existing configuration-space geometry only for these rounded pairs.
        for candidate in _space(world).bb_query(mine.cache_bb(), mine.filter):
            if not isinstance(mine, pymunk.Circle) and not isinstance(candidate, pymunk.Circle):
                continue
            if not _allowed(world, mine, candidate, False):
                continue
            tangent = _tangent(mine, candidate)
            if tangent is not None:
                tangent_point, tangent_normal = tangent
                record(candidate, tangent_point, tangent_normal)


def _contacts(stage: Stage) -> dict[tuple[Actor, CastTarget], Collision]:
    """Combine accepted solver evidence with exact non-solver/sensor geometry."""
    world = stage._physics
    if world is None or not stage._hit_handlers:
        return {}
    owners: dict[pymunk.Body, CastTarget] = {
        body._native: body._actor for body in world._bodies if body._native is not None
    }
    owners.update(
        {
            terrain.native: terrain.tilemap
            for terrain in world._terrain
            if terrain.native is not None
        }
    )
    receivers = tuple(dict.fromkeys(h.actor for h in stage._hit_handlers if h.actor is not None))
    result: dict[tuple[Actor, CastTarget], Collision] = {}
    for actor in receivers:
        if actor._stage is stage and isinstance(actor._transform, Body):
            _actor_contacts(world, actor, owners, result)
    return result


def _sample(
    stage: Stage,
    swept: tuple[tuple[Body, Collision], ...],
    seen: set[tuple[Actor, CastTarget]],
) -> tuple[tuple[Actor, Collision], ...]:
    """Advance episode history and queue at most one event per pair in this tick."""
    from .puppets import Puppet
    from .sprites import Sprite

    previous = stage._hit_contacts
    current = _contacts(stage)
    registered = {h.actor for h in stage._hit_handlers}
    events = {key: collision for key, collision in current.items() if key not in previous}
    for body, collision in swept:
        actor, target = body._actor, collision.target
        blocking = not isinstance(target, (Sprite, Puppet)) or not target.body.sensor
        key = actor, target
        if actor in registered and (blocking or key not in previous):
            events[key] = collision
        if isinstance(target, (Sprite, Puppet)) and target in registered:
            key = target, actor
            if blocking or key not in previous:
                nx, ny = collision.normal
                events[key] = Collision(actor, collision.point, (-nx, -ny), None)
    order = {obj: index for index, obj in enumerate(stage._members)}
    output = tuple(
        (actor, events[actor, other])
        for actor, other in sorted(events, key=lambda pair: (order[pair[0]], order[pair[1]]))
        if (actor, other) not in seen
    )
    seen.update((actor, collision.target) for actor, collision in output)
    if len(current) > _MAX_CONTACTS or len(seen) > _MAX_CONTACTS:
        raise StageError("Physical contacts exceeded the 8192-pair/event limit")
    stage._hit_contacts = set(current)
    return output


def _dispatch(stage: Stage, impacts: tuple[tuple[Actor, Collision], ...]) -> None:
    """Deliver after stepping; callbacks may safely remove either collision owner."""
    from ._scripts import _trigger

    handlers = tuple(stage._hit_handlers)
    for actor, collision in impacts:
        for handler in handlers:
            if not stage.running or stage.paused:
                return
            if (
                handler.actor is actor
                and actor._stage is stage
                and collision.target._stage is stage
            ):
                _trigger(stage, handler, collision)


def _prune(stage: Stage, owner: CastTarget) -> None:
    stage._hit_contacts = {
        pair for pair in stage._hit_contacts if pair[0] is not owner and pair[1] is not owner
    }


def _bind(actor: Actor, work: object, busy: WhenBusy) -> object:
    from .scripts import Script
    from .stage import _attached, _work_handler

    stage = _attached(actor)
    if work is not None:
        if len(stage._hit_handlers) >= 1024:
            raise StageError("A stage supports at most 1024 hit handlers")
        stage._hit_handlers.append(_work_handler(stage, actor, work, busy))
        return None if isinstance(work, Script) else work

    def decorate(callback: object) -> object:
        return _bind(actor, callback, busy)

    return decorate
