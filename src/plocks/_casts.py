"""Read-only world casts; native broad phase and all query scratch are operation-local."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from .geometry import Point, _number, _point, _positive, _rotate, distance
from .physics import Body, Box, Circle, Physics, _native
from .queries import CastHit, CastIgnore, CastTarget

if TYPE_CHECKING:
    import pymunk


def _filter(ignore: CastIgnore) -> Callable[[CastTarget], bool]:
    """Snapshot iterable exclusions or validate one pure typed predicate."""
    from .puppets import Puppet
    from .sprites import Sprite
    from .tiling import TileMap

    if callable(ignore):

        def predicate(target: CastTarget) -> bool:
            result = ignore(target)
            if not isinstance(result, bool):
                from .stage import _reject_result

                _reject_result(result, "ignore must return bool from a synchronous predicate")
            return result

        return predicate
    skipped = () if ignore is None else tuple(ignore)
    if any(not isinstance(value, (Sprite, Puppet, TileMap)) for value in skipped):
        raise TypeError("ignore must contain actors or tilemaps")
    return lambda target: any(target is value for value in skipped)


def _source(
    shape: Box | Circle | None, direction: float, scale: float
) -> tuple[tuple[Point, ...], float]:
    """Transform a moving convex core relative to its anchor once for this query."""
    direction = _number(direction, "direction")
    scale = _positive(scale, "scale")
    if shape is None:
        return ((0.0, 0.0),), 0.0
    if isinstance(shape, Circle):
        return (_point(_rotate(shape.center, direction, scale)),), _positive(
            shape.radius * scale, "radius"
        )
    if not isinstance(shape, Box):
        raise TypeError("Use a Box or Circle")
    x, y = shape.center
    return tuple(
        _point(_rotate((x + sx * shape.width / 2, y + sy * shape.height / 2), direction, scale))
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))
    ), 0.0


def _candidates(
    world: Physics, start: Point, end: Point, offsets: tuple[Point, ...], radius: float
) -> list[tuple[CastTarget, pymunk.Shape, tuple[int, int] | None]]:
    """Use the native spatial index, then order by stage insertion and tile cell."""
    import pymunk

    from ._physics import _space

    xs = [p[0] for p in offsets]
    ys = [p[1] for p in offsets]
    low = _point(
        (min(start[0], end[0]) + min(xs) - radius, min(start[1], end[1]) + min(ys) - radius)
    )
    high = _point(
        (max(start[0], end[0]) + max(xs) + radius, max(start[1], end[1]) + max(ys) + radius)
    )
    shapes = _space(world).bb_query(pymunk.BB(*low, *high), pymunk.ShapeFilter())
    owners: dict[pymunk.Body, CastTarget] = {
        body._native: body._actor for body in world._bodies if body._native is not None
    }
    owners.update({item.native: item.tilemap for item in world._terrain if item.native is not None})
    order = {obj: index for index, obj in enumerate(world._stage._members)}
    from .tiling import TileMap

    result: list[tuple[CastTarget, pymunk.Shape, tuple[int, int] | None]] = []
    for native in shapes:
        target = owners.get(native.body) if native.body is not None else None
        if target is None or native.sensor:
            continue
        cell = None
        if isinstance(target, TileMap):
            if isinstance(native, pymunk.Segment):
                # One-way geometry lies exactly on a cell edge. Derive from
                # native local coordinates to avoid world-offset rounding.
                w, h = target.tile_size
                cell = round(-native.a.y / h), round(native.a.x / w)
            else:
                bb = native.cache_bb()
                cell = target.cell_at(x=(bb.left + bb.right) / 2, y=(bb.bottom + bb.top) / 2)
        result.append((target, native, cell))
    result.sort(key=lambda item: (order[item[0]], item[2] or (-1, -1)))
    return result


def _cast(
    world: Physics,
    shape: Box | Circle | None,
    start: Point,
    end: Point,
    direction: float,
    scale: float,
    ignore: CastIgnore,
    own: Body | None = None,
) -> CastHit | None:
    """Return the nearest continuous hit without mutating native geometry or actors."""
    from ._physics import _ONE_WAY, _space
    from ._sweep import _sweep

    space = _space(world)
    start, end = _point(start, "start"), _point(end, "end")
    length = distance(start, end)
    offsets, radius = _source(shape, direction, scale)
    if own is not None:
        from ._sweep import _core

        core, radius = _core(next(iter(_native(own).shapes)))
        offsets = tuple(_point((x - start[0], y - start[1])) for x, y in core)
    skipped = _filter(ignore)
    decisions: dict[CastTarget, bool] = {}
    best: CastHit | None = None
    for target, native, cell in _candidates(world, start, end, offsets, radius):
        if own is not None and target is own._actor:
            continue
        if target not in decisions:
            decisions[target] = skipped(target)
        if decisions[target]:
            continue
        if shape is not None and native.collision_type == _ONE_WAY:
            bottom = start[1] + min(p[1] for p in offsets) - radius
            if end[1] >= start[1] or bottom < native.bb.top - 2 * space.collision_slop:
                continue
        hit = _sweep(
            native,
            start,
            end,
            offsets,
            radius,
            movement=shape is not None,
            slop=2 * float(space.collision_slop),
        )
        if hit is not None:
            fraction, point, normal = hit
            travelled = _number(fraction * length, "hit distance")
            if best is None or travelled < best.distance - 1e-8:
                best = CastHit(target, point, normal, travelled, cell)
    return best


def _body_cast(
    body: Body, distance: float, direction: float | None, ignore: CastIgnore
) -> CastHit | None:
    """Sweep the attached current collider, automatically excluding its own owner."""
    _native(body)
    amount = _number(distance, "distance", minimum=0)
    heading = body._actor.direction if direction is None else _number(direction, "direction")
    start = body._actor.position
    dx, dy = _rotate((amount, 0), heading)
    end = _point((start[0] + dx, start[1] + dy), "destination")
    return _cast(
        body._world, body.shape, start, end, body._actor.direction, body._actor.scale, ignore, body
    )
