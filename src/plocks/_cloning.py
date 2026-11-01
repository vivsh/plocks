"""Actor copies and inherited registrations; progress stays with existing owners."""

from __future__ import annotations

from collections.abc import Callable
from copy import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from ._scripts import _Handler, _InputBinding, _trigger
from .errors import StageError
from .physics import Body, BodyType
from .puppets import Puppet
from .sprites import Sprite

if TYPE_CHECKING:
    from ._commands import Actor
    from .stage import Stage


@dataclass(frozen=True, slots=True)
class _CloneStart:
    source: Sprite | Puppet
    target: Sprite | Puppet


def _stage_for_clone(source: Actor) -> Stage:
    """Check membership and the derived quota before acquiring any clone resources."""
    stage = source._stage
    if stage is None or stage._state == "closed":
        raise StageError("Clone an actor attached to an open stage")
    _check_quota(stage)
    return stage


def _check_quota(stage: Stage) -> None:
    """Enforce the same derived quota for new clones and explicit re-additions."""
    if sum(isinstance(obj, (Sprite, Puppet)) and obj.is_clone for obj in stage._members) >= 300:
        raise StageError("Cannot add clone: the stage already has 300 clones")


def _copy_actor(source: Actor) -> Actor:
    """Construct engine-owned state explicitly; never copy a live actor object graph."""
    if type(source) not in (Sprite, Puppet):
        raise TypeError("Custom actor subclasses must implement their own clone factory")
    state = copy(source.state)
    if source.state is not None and (
        state is source.state or type(state) is not type(source.state)
    ):
        raise TypeError("Copying actor state must produce a distinct instance of the same type")
    target: Actor
    if isinstance(source, Sprite):
        target = cast(
            Sprite[object],
            Sprite(source.image, body_type=source.body_type, one_way=source.one_way),
        )
    else:
        target = cast(
            Puppet[object],
            Puppet(
                source.skeleton, parts=source.parts, pose=source.pose, body_type=source.body_type
            ),
        )
    target.position = source.position
    target.direction = source.direction
    target.scale = source.scale
    target.visible = source.visible
    target.layer = source.layer
    target.rotation_style = source.rotation_style
    target._state = state
    target._clone_source = source
    return target


def _copy_physics(source: Actor, target: Actor) -> None:
    """Copy configuration, leaving native resources, contacts and motion independent."""
    if not isinstance(source._transform, Body):
        return
    before, after = source.body, target.body
    if not before.auto_shape:
        after.shape = before.shape
    after.friction = before.friction
    after.drag = before.drag
    after.bounce = before.bounce
    after.sensor = before.sensor
    after.collision_group = before.collision_group
    after.collides_with = before.collides_with
    after.projectile = before.projectile
    if source.body_type is BodyType.DYNAMIC:
        after.mass = before.mass
        after.rotation_locked = before.rotation_locked


def _inherit(stage: Stage, source: Actor, target: Actor) -> None:
    """Snapshot actor bindings with fresh busy/repeat state and receiver-neutral adapters."""
    handlers: dict[_Handler, _Handler] = {}

    def inherited(handler: _Handler) -> _Handler:
        if handler not in handlers:
            handlers[handler] = _Handler(handler.start, target, handler.when_busy)
        return handlers[handler]

    def inherit_inputs[Key](registry: dict[Key, list[_InputBinding]]) -> None:
        for bindings in tuple(registry.values()):
            bindings.extend(
                _InputBinding(inherited(binding.handler), binding.repeat)
                for binding in tuple(bindings)
                if binding.handler.actor is source
            )

    from ._touches import _inherit as inherit_touches

    inherit_touches(stage, source, target, inherited)
    inherit_inputs(stage._gamepad_handlers)
    for callbacks in tuple(stage._gamepad_up_handlers.values()):
        callbacks.extend(
            inherited(handler) for handler in tuple(callbacks) if handler.actor is source
        )
    clicks = stage._clicks.get(source, ())
    if clicks:
        stage._clicks[target] = [inherited(handler) for handler in tuple(clicks)]
    for callbacks in tuple(stage._message_handlers.values()):
        callbacks.extend(
            inherited(handler) for handler in tuple(callbacks) if handler.actor is source
        )
    if len(stage._hit_handlers) + sum(h.actor is source for h in stage._hit_handlers) > 1024:
        raise StageError("A stage supports at most 1024 hit handlers")
    if (
        len(stage._clone_end_handlers) + sum(h.actor is source for h in stage._clone_end_handlers)
        > 1024
    ):
        raise StageError("A stage supports at most 1024 clone-end handlers")
    stage._clone_end_handlers.extend(
        inherited(h) for h in tuple(stage._clone_end_handlers) if h.actor is source
    )
    stage._hit_handlers.extend(
        inherited(h) for h in tuple(stage._hit_handlers) if h.actor is source
    )
    stage._clone_handlers.extend(
        inherited(handler) for handler in tuple(stage._clone_handlers) if handler.actor is source
    )
    stage._updates.extend(
        (target, callback) for actor, callback in tuple(stage._updates) if actor is source
    )


def _clone(source: Actor) -> Actor:
    """Prepare a detached copy, commit membership/bindings, and roll back on failure."""
    stage = _stage_for_clone(source)
    target = _copy_actor(source)
    if _stage_for_clone(source) is not stage:
        raise StageError("The source changed stages while its state was being copied")
    try:
        stage.add(target)
        _copy_physics(source, target)
        _inherit(stage, source, target)
        stage._pending.append(_CloneStart(source, target))
    except BaseException as error:
        # A failed clone was never delivered to its author; suppress end events
        # while still retiring any partially inherited registrations.
        try:
            _forget(stage, target)
            if target in stage._members:
                stage.remove(target)
            else:
                if isinstance(target._transform, Body):
                    from ._physics import _retire

                    _retire(target._transform)
                target._stage = None
                _forget(stage, target)
        except BaseException as cleanup:  # noqa: BLE001 -- preserve primary failure after rollback
            error.add_note(f"Clone cleanup also failed: {cleanup!r}")
        raise
    return target


def _start_clone(stage: Stage, event: _CloneStart) -> None:
    """Dispatch once without adopting clone behaviors into the source's action tree."""
    if event.target._stage is not stage:
        return
    for handler in tuple(stage._clone_handlers):
        if not stage.running or event.target._stage is not stage:
            break
        if handler.actor is event.target:
            _trigger(stage, handler, source=event.source)


def _prune[K, V](registry: dict[K, list[V]], keep: Callable[[V], bool]) -> None:
    """Remove a clone's registrations and empty keys without retaining a reverse index."""
    for key, entries in tuple(registry.items()):
        entries[:] = [entry for entry in entries if keep(entry)]
        if not entries:
            del registry[key]


def _forget(stage: Stage, actor: Actor) -> None:
    """Retire all clone registrations and queued starts; ordinary actors keep theirs."""
    _prune(stage._gamepad_handlers, lambda binding: binding.handler.actor is not actor)
    _prune(stage._gamepad_up_handlers, lambda handler: handler.actor is not actor)
    stage._hit_handlers[:] = [h for h in stage._hit_handlers if h.actor is not actor]
    _prune(stage._clicks, lambda handler: handler.actor is not actor)
    _prune(stage._message_handlers, lambda handler: handler.actor is not actor)
    stage._starts[:] = [handler for handler in stage._starts if handler.actor is not actor]
    stage._clone_end_handlers[:] = [h for h in stage._clone_end_handlers if h.actor is not actor]
    stage._clone_handlers[:] = [
        handler for handler in stage._clone_handlers if handler.actor is not actor
    ]
    stage._updates[:] = [
        (owner, callback) for owner, callback in stage._updates if owner is not actor
    ]
    stage._pending[:] = [
        event
        for event in stage._pending
        if not isinstance(event, _CloneStart) or event.target is not actor
    ]


def _count_clones(stage: Stage, source: Actor | None = None) -> int:
    """Derive live counts without a counter or reverse-provenance index."""
    return sum(
        isinstance(actor, (Sprite, Puppet))
        and actor.is_clone
        and (source is None or actor._clone_source is source)
        for actor in stage._members
    )


def _register_end(actor: Actor, callback: object) -> None:
    from ._scripts import WhenBusy
    from .stage import _attached, _callback_handler

    stage = _attached(actor)
    if len(stage._clone_end_handlers) >= 1024:
        raise StageError("A stage supports at most 1024 clone-end handlers")
    stage._clone_end_handlers.append(_callback_handler(callback, actor, WhenBusy.IGNORE))


def _notify_end(stage: Stage, actor: Actor, handlers: tuple[_Handler, ...]) -> None:
    """Notify only after successful detachment; cleanup/rollback never spawn work."""
    from .events import Event
    from .stage import _check_callback_result

    source = actor._clone_source
    if source is None:
        return
    for handler in handlers:
        if stage._state == "closed":
            break
        try:
            _check_callback_result(handler.start(Event(source, actor, None)), "clone_end")
        except BaseException as error:
            try:
                stage.stop()
            except BaseException as cleanup:  # noqa: BLE001 -- preserve the original callback failure
                error.add_note(f"Stopping after clone-end failure also failed: {cleanup!r}")
            raise
