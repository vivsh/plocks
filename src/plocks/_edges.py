"""Stage-owned edge transitions; current geometry and dispatch batches stay local."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ._scripts import WhenBusy, _Handler, _trigger
from .errors import StageError
from .geometry import Bounds, Edge

if TYPE_CHECKING:
    from ._commands import Actor
    from .stage import Stage


@dataclass(slots=True, eq=False)
class _EdgeWatch:
    actor: Actor
    bounds: Bounds | None
    handlers: list[_Handler]
    previous: frozenset[Edge]


def _validate(bounds: Bounds | None) -> None:
    if bounds is not None and not isinstance(bounds, Bounds):
        raise TypeError("Use Bounds, or omit bounds for the current viewport")


def _which(actor: Actor, bounds: Bounds | None) -> frozenset[Edge]:
    """Derive reached half-spaces; outside actors still count beyond the crossed sides."""
    _validate(bounds)
    if bounds is None:
        if actor._stage is None or actor._stage._state == "closed":
            raise StageError("Supply Bounds or add the actor to an open stage")
        bounds = actor._stage.world_bounds
    box = actor.bounds
    return frozenset(
        edge
        for edge, reached in (
            (Edge.LEFT, box.left <= bounds.left),
            (Edge.RIGHT, box.right >= bounds.right),
            (Edge.TOP, box.top >= bounds.top),
            (Edge.BOTTOM, box.bottom <= bounds.bottom),
        )
        if reached
    )


def _register(actor: Actor, bounds: Bounds | None, work: object, busy: WhenBusy) -> None:
    from .stage import _attached, _work_handler

    _validate(bounds)
    stage = _attached(actor)
    handler = _work_handler(stage, actor, work, busy)
    if sum(len(w.handlers) for w in stage._edges) >= 1024:
        raise StageError("A stage supports at most 1024 edge handlers")
    watch = next((w for w in stage._edges if w.actor is actor and w.bounds == bounds), None)
    if watch is None:
        watch = _EdgeWatch(actor, bounds, [], frozenset())
        stage._edges.append(watch)
    watch.handlers.append(handler)


def _bind(actor: Actor, bounds: Bounds | None, script: object, busy: WhenBusy) -> object:
    """Accept the existing Script binding or return a receiver-preserving decorator."""
    _validate(bounds)
    if script is not None:
        _register(actor, bounds, script, busy)
        return None

    def decorate(callback: object) -> object:
        _register(actor, bounds, callback, busy)
        return callback

    return decorate


def _sample(stage: Stage) -> None:
    """Snapshot all newly reached edges after camera following, then deliver in order."""
    if not stage.running or stage.paused:
        return
    batch: list[tuple[_EdgeWatch, frozenset[Edge], tuple[_Handler, ...]]] = []
    for watch in tuple(stage._edges):
        if watch.actor._stage is not stage:
            watch.previous = frozenset()
            continue
        current = _which(watch.actor, watch.bounds)
        if current - watch.previous:
            batch.append((watch, current, tuple(watch.handlers)))
        watch.previous = current
    for watch, edges, handlers in batch:
        for handler in handlers:
            if not stage.running or stage.paused:
                return
            if watch.actor._stage is stage and watch in stage._edges and watch.previous is edges:
                _trigger(stage, handler, edges)


def _detach(stage: Stage, actor: Actor) -> None:
    """Reset ordinary subscriptions; clone subscriptions retire with their receiver."""
    for watch in stage._edges:
        if watch.actor is actor:
            watch.previous = frozenset()
    if actor.is_clone:
        stage._edges[:] = [watch for watch in stage._edges if watch.actor is not actor]


def _inherit(
    stage: Stage, source: Actor, target: Actor, handler: Callable[[_Handler], _Handler]
) -> None:
    """Copy listeners and immutable bounds, with fresh side history and independent busy state."""
    originals = tuple(watch for watch in stage._edges if watch.actor is source)
    count = sum(len(watch.handlers) for watch in stage._edges)
    if count + sum(len(watch.handlers) for watch in originals) > 1024:
        raise StageError("A stage supports at most 1024 edge handlers")
    stage._edges.extend(
        _EdgeWatch(target, watch.bounds, [handler(h) for h in watch.handlers], frozenset())
        for watch in originals
    )
