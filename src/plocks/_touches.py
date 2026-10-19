"""Registered overlap transitions; each ordered pair owns one previous result."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from ._scripts import WhenBusy, _Handler, _trigger
from .errors import StageError

if TYPE_CHECKING:
    from ._commands import Actor
    from .stage import Stage
    from .tiling import TileMap


@dataclass(slots=True, eq=False)
class _TouchWatch:
    actor: Actor
    other: Actor | TileMap
    enters: list[_Handler]
    leaves: list[_Handler]
    was_touching: bool


def _register(actor: Actor, other: object, work: object, leave: bool, busy: WhenBusy) -> None:
    """Validate before admitting a pair or changing its ordered listeners."""
    from .puppets import Puppet
    from .sprites import Sprite
    from .stage import _attached, _work_handler
    from .tiling import TileMap

    stage = _attached(actor)
    if not isinstance(other, (Sprite, Puppet, TileMap)):
        raise TypeError("Touch events require a Sprite, Puppet or TileMap")
    if other is actor:
        raise ValueError("An actor cannot watch itself")
    if other._stage is not stage:
        raise StageError("Both touch objects must belong to the same stage")
    handler = _work_handler(stage, actor, work, busy)
    watch = next((w for w in stage._touches if w.actor is actor and w.other is other), None)
    if watch is None:
        if len(stage._touches) >= 1024:
            raise StageError("A stage supports at most 1024 watched touch pairs")
        watch = _TouchWatch(actor, cast("Actor | TileMap", other), [], [], False)
        stage._touches.append(watch)
    (watch.leaves if leave else watch.enters).append(handler)


def _bind(actor: Actor, other: object, script: object, leave: bool, busy: WhenBusy) -> object:
    """Return the normal decorator or admit a direct Script binding."""
    if script is not None:
        _register(actor, other, script, leave, busy)
        return None

    def decorate(callback: object) -> object:
        _register(actor, other, callback, leave, busy)
        return callback

    return decorate


def _sample(stage: Stage) -> None:
    """Snapshot all transitions before callbacks can mutate world membership."""
    batch: list[tuple[_TouchWatch, tuple[_Handler, ...]]] = []
    for watch in tuple(stage._touches):
        if watch.actor._stage is not stage or watch.other._stage is not stage:
            watch.was_touching = False
            continue
        touching = watch.actor.touching(watch.other)
        if touching != watch.was_touching:
            batch.append((watch, tuple(watch.enters if touching else watch.leaves)))
        watch.was_touching = touching
    for watch, handlers in batch:
        for handler in handlers:
            if not stage.running:
                return
            if watch.actor._stage is stage and watch.other._stage is stage:
                _trigger(stage, handler, watch.other)


def _detach(stage: Stage, actor: Actor | TileMap) -> None:
    """Removal resets ordinary history and retires every watch involving a clone."""
    from .puppets import Puppet
    from .sprites import Sprite

    for watch in stage._touches:
        if watch.actor is actor or watch.other is actor:
            watch.was_touching = False
    if isinstance(actor, (Sprite, Puppet)) and actor.is_clone:
        stage._touches[:] = [
            w for w in stage._touches if w.actor is not actor and w.other is not actor
        ]


def _inherit(
    stage: Stage, source: Actor, target: Actor, handler: Callable[[_Handler], _Handler]
) -> None:
    """Clone the receiver's registrations, sharing no overlap history."""
    originals = tuple(w for w in stage._touches if w.actor is source)
    if len(stage._touches) + len(originals) > 1024:
        raise StageError("A stage supports at most 1024 watched touch pairs")
    stage._touches.extend(
        _TouchWatch(
            target, w.other, [handler(h) for h in w.enters], [handler(h) for h in w.leaves], False
        )
        for w in originals
    )
