"""Opt-in bullet sweeps; pose snapshots and impact batches live for one integration."""

from __future__ import annotations

from math import hypot
from typing import TYPE_CHECKING

from .geometry import Point, _point
from .physics import Body, Physics, _native
from .queries import CastHit

if TYPE_CHECKING:
    from ._commands import Actor
    from ._scripts import WhenBusy
    from .stage import Stage


def _hits(world: Physics, starts: dict[Body, Point]) -> tuple[tuple[Body, CastHit], ...]:
    """Sweep translating projectiles relative to the other bodies' translation."""
    from ._casts import _candidates
    from ._combat import _pair
    from ._physics import _ONE_WAY, _space
    from ._sweep import _core, _sweep

    shifts = {
        _native(body): (body._actor.x - point[0], body._actor.y - point[1])
        for body, point in starts.items()
    }
    reach = max((hypot(*shift) for shift in shifts.values()), default=0.0)
    impacts: list[tuple[Body, CastHit]] = []
    for body, start in starts.items():
        if not body._projectile:
            continue
        end = body._actor.position
        length = hypot(end[0] - start[0], end[1] - start[1])
        if not length:
            continue
        source = _native(body)
        core, radius = _core(next(iter(source.shapes)))
        offsets = tuple((x - end[0], y - end[1]) for x, y in core)
        best: tuple[float, CastHit] | None = None
        for target, shape, cell in _candidates(world, start, end, offsets, radius + reach):
            native = shape.body
            if native is None or native is source or not _pair(world, source, native):
                continue
            dx, dy = shifts.get(native, (0.0, 0.0))
            relative_start = _point((start[0] + dx, start[1] + dy))
            if shape.collision_type == _ONE_WAY:
                bottom = relative_start[1] + min(y for _, y in offsets) - radius
                if (
                    end[1] >= relative_start[1]
                    or bottom < shape.bb.top - 2 * _space(world).collision_slop
                ):
                    continue
            hit = _sweep(
                shape,
                relative_start,
                end,
                offsets,
                radius,
                movement=True,
                slop=2 * float(_space(world).collision_slop),
            )
            if hit is not None:
                fraction, point, normal = hit
                point = (point[0] - dx * (1 - fraction), point[1] - dy * (1 - fraction))
                result = CastHit(target, point, normal, fraction * length, cell)
                if best is None or fraction < best[0] - 1e-8:
                    best = fraction, result
        if best is not None:
            fraction, result = best
            # Sensor bullets impart no solver forces; position is clamped only after
            # choosing the nearest collision against this substep's geometry.
            source.position = (
                start[0] + (end[0] - start[0]) * fraction,
                start[1] + (end[1] - start[1]) * fraction,
            )
            source.velocity = (0, 0)
            _space(world).reindex_shapes_for_body(source)
            impacts.append((body, result))
    return tuple(impacts)


def _dispatch(stage: Stage, impacts: tuple[tuple[Body, CastHit], ...]) -> None:
    """Deliver immutable impacts outside native stepping, using normal busy rules."""
    from ._scripts import _trigger

    handlers = tuple(stage._hit_handlers)
    for body, hit in impacts:
        for handler in handlers:
            if not stage.running:
                return
            if handler.actor is body._actor and body._actor._stage is stage:
                _trigger(stage, handler, hit)


def _bind(actor: Actor, work: object, busy: WhenBusy) -> object:
    from .scripts import Script
    from .stage import _attached, _work_handler

    stage = _attached(actor)
    if work is not None:
        if len(stage._hit_handlers) >= 1024:
            from .errors import StageError

            raise StageError("A stage supports at most 1024 hit handlers")
        stage._hit_handlers.append(_work_handler(stage, actor, work, busy))
        return None if isinstance(work, Script) else work

    def decorate(callback: object) -> object:
        return _bind(actor, callback, busy)

    return decorate
