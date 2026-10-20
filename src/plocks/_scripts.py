"""Bounded stage-owned coroutine trees; traversal scratch never becomes a scheduler cache."""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Iterator
from dataclasses import dataclass, field
from enum import Enum
from types import CoroutineType
from typing import TYPE_CHECKING

from ._operations import (
    _AwaitAction,
    _AwaitAll,
    _BubbleRun,
    _Context,
    _deadline,
    _Delay,
    _Delivery,
    _During,
    _ForceRun,
    _freeze,
    _Glide,
    _ImageRun,
    _JoinDelivery,
    _PoseRun,
    _Request,
    _sample_glide,
    _SoundWait,
    _TorqueRun,
)
from .actions import Action, _Completion, _Outcome, _Queued
from .errors import ActionCancelled, StageError
from .events import Event

if TYPE_CHECKING:
    from ._commands import Actor, _Command
    from .puppets import Puppet
    from .sprites import Sprite
    from .stage import Stage


class WhenBusy(Enum):
    """Ignore repeated triggers, or cancel the previous invocation and restart."""

    IGNORE = "ignore"
    RESTART = "restart"


@dataclass(eq=False, slots=True)
class _Handler:
    start: Callable[
        [Event[Stage | Sprite | Puppet, object]],
        _Command[Actor] | Action | None,
    ]
    actor: Sprite | Puppet | None
    when_busy: WhenBusy


@dataclass(eq=False, slots=True)
class _InputBinding:
    handler: _Handler
    repeat: float | None
    next_repeat: float | None = None


@dataclass(eq=False, slots=True)
class _Fiber:
    coroutine: Coroutine[object, object, None] | None
    waiting: _Request | None = None
    children: list[Action] = field(default_factory=list[Action])


def _branches(fiber: _Fiber) -> Iterator[_Fiber]:
    yield fiber
    if isinstance(fiber.waiting, _During):
        yield from _branches(fiber.waiting.foreground)
        yield from _branches(fiber.waiting.background)


def _walk(action: Action) -> Iterator[Action]:
    yield action
    if isinstance(action._state, _Fiber):
        for fiber in _branches(action._state):
            for child in tuple(fiber.children):
                yield from _walk(child)


def _actions(stage: Stage) -> tuple[Action, ...]:
    return tuple(child for root in tuple(stage._actions) for child in _walk(root))


def _fibers(action: Action) -> Iterator[_Fiber]:
    for child in _walk(action):
        if isinstance(child._state, _Fiber):
            yield from _branches(child._state)


def _outer(action: Action) -> Action:
    for root in action._stage._actions:
        if any(child is action for child in _walk(root)):
            return root
    return action


def _count(stage: Stage) -> int:
    return sum(
        1 if not isinstance(a._state, _Fiber) else sum(1 for _ in _branches(a._state))
        for a in _actions(stage)
    )


def _admit(
    stage: Stage,
    coroutine: Coroutine[object, object, None],
    actor: Sprite | Puppet | None,
    handler: _Handler | None = None,
    *,
    after: Action | None = None,
) -> Action:
    if stage._state == "closed" or _count(stage) >= 128:
        coroutine.close()
        raise StageError("Cannot schedule action: stage closed or 128-execution limit reached")
    if after is not None and after._stage is not stage:
        coroutine.close()
        raise StageError("after must reference an action from the same stage")
    action = object.__new__(Action)
    action._stage, action._actor, action._after = stage, actor, after
    action._parent, action._handler = None, handler
    action._state = _Queued(coroutine, stage.time)
    stage._actions.append(action)
    if after is not None and after.cancelled:
        _cancel(stage, action)
    return action


def _adopt(stage: Stage, fiber: _Fiber, before: tuple[Action, ...]) -> None:
    for child in tuple(stage._actions):
        if child not in before:
            stage._actions.remove(child)
            child._parent = fiber
            fiber.children.append(child)


def _finish(action: Action, result: _Outcome | BaseException, at: float) -> None:
    if action.done:
        return
    state = action._state
    siblings = action._stage._actions if action._parent is None else action._parent.children
    if action in siblings:
        siblings.remove(action)
    action._state = _Completion(at, result)
    action._parent = None
    action._after = None
    action._handler = None
    if isinstance(state, _Queued):
        state.work.close()
    elif isinstance(state, _Fiber):
        _close_fiber(action._stage, state)


def _close_fiber(stage: Stage, fiber: _Fiber) -> None:
    request = fiber.waiting
    errors: list[BaseException] = []
    for child in tuple(fiber.children):
        try:
            _cancel(stage, child)
        except BaseException as error:  # noqa: BLE001 -- finish every owned child before re-raising
            errors.append(error)
    if isinstance(request, _During):
        for branch in (request.background, request.foreground):
            try:
                _close_fiber(stage, branch)
            except BaseException as error:  # noqa: BLE001 -- finish cleanup and re-raise the original failure
                errors.append(error)
    _freeze(request, stage.time, cancel=True)
    coroutine = fiber.coroutine
    if coroutine is not None and not (
        isinstance(coroutine, CoroutineType) and coroutine.cr_running
    ):
        fiber.coroutine = None
        fiber.waiting = None
        try:
            coroutine.close()
        except BaseException as error:  # noqa: BLE001 -- finish cleanup and re-raise the original failure
            errors.append(error)
    if errors:
        raise errors[0]


def _cancel(stage: Stage, root: Action) -> None:
    if root.done:
        return
    dependents = [a for a in _actions(stage) if a._after is root]
    try:
        _finish(root, _Outcome.CANCELLED, stage.time)
    finally:
        for action in dependents:
            _cancel(stage, action)


async def _observe(action: Action) -> None:
    from ._commands import _join

    await _join((action,))


def _trigger(
    stage: Stage,
    handler: _Handler,
    data: object = None,
    *,
    delivery: _Delivery | None = None,
    source: Stage | Sprite | Puppet | None = None,
) -> Action | None:
    if not stage.running or (handler.actor is not None and handler.actor._stage is not stage):
        return None
    busy = [a for a in _actions(stage) if a._handler is handler]
    if busy and handler.when_busy is WhenBusy.IGNORE:
        return None
    for action in busy:
        _cancel(stage, action)
    before = _actions(stage)
    target = stage if handler.actor is None else handler.actor
    occurrence = (
        Event(stage if source is None else source, target, data)
        if delivery is None
        else Event(delivery.source, target, delivery.data)
    )
    result = handler.start(occurrence)
    if result is None:
        return None
    if handler.actor is not None and handler.actor._stage is not stage:
        raise StageError("The receiving actor was detached during its callback")
    if isinstance(result, Action):
        if result._stage is not stage:
            raise StageError("A handler must return an action from its own stage")
        action = _admit(stage, _observe(result), handler.actor, handler)
        queued = action._state
        assert isinstance(queued, _Queued)
        fiber = _Fiber(queued.work)
        action._state = fiber
        _adopt(stage, fiber, (*before, action))
        return action
    if handler.actor is None:
        raise StageError("A returned Script requires a receiving actor")
    action = _admit(stage, result.run(handler.actor), handler.actor, handler)
    queued = action._state
    assert isinstance(queued, _Queued)
    fiber = _Fiber(queued.work)
    action._state = fiber
    _adopt(stage, fiber, (*before, action))
    return action


def _conflicts(
    actor: Sprite | Puppet,
    x: bool,
    y: bool,
    current: Action | None = None,
    *,
    visual: bool = False,
    bubble: bool = False,
) -> None:
    stage = actor._stage
    if stage is None:
        return
    for root in tuple(stage._actions):
        for fiber in tuple(_fibers(root)):
            request = fiber.waiting
            if (
                not isinstance(request, (_Glide, _ImageRun, _PoseRun, _BubbleRun))
                or request.actor is not actor
            ):
                continue
            deadline = _deadline(request)
            if deadline is not None and deadline <= stage.time + 1e-12:
                continue
            overlap = (
                (bubble and isinstance(request, _BubbleRun))
                or (visual and isinstance(request, (_ImageRun, _PoseRun)))
                or (
                    isinstance(request, _Glide)
                    and ((x and request.x is not None) or (y and request.y is not None))
                )
            )
            if overlap:
                if current is not None and root is _outer(current):
                    raise StageError("During branches cannot control the same property")
                _cancel(stage, root)
                break


def _detach(stage: Stage, actor: Sprite | Puppet) -> None:
    affected = [
        root
        for root in stage._actions
        if any(action._actor is actor for action in _walk(root))
        or any(
            isinstance(f.waiting, (_Glide, _ImageRun, _PoseRun, _BubbleRun))
            and f.waiting.actor is actor
            for f in _fibers(root)
        )
    ]
    # Freeze while the association is still valid; reject re-admission during cleanup.
    for root in affected:
        for fiber in _fibers(root):
            _freeze(fiber.waiting, stage.time, cancel=True)
    for delivery in tuple(stage._messages):
        if delivery.source is actor or delivery.destination is actor:
            delivery.receivers = ()
            stage._messages.remove(delivery)
    actor._stage = None
    errors: list[BaseException] = []
    try:
        for root in affected:
            try:
                _cancel(stage, root)
            except BaseException as error:  # noqa: BLE001 -- finish all detach cleanup before re-raising
                errors.append(error)
    finally:
        actor._bubble = None
        from .physics import Body

        if isinstance(actor._transform, Body):
            from ._physics import _retire

            _retire(actor._transform)
    if errors:
        raise errors[0]


def _sample(stage: Stage) -> None:
    for root in tuple(stage._actions):
        for fiber in _fibers(root):
            if isinstance(fiber.waiting, _Glide):
                _sample_glide(fiber.waiting, stage.time)


def _deliver(stage: Stage) -> None:
    pending = tuple(stage._messages)
    stage._messages.clear()
    for delivery in pending:
        source = delivery.source
        if (source is not stage and getattr(source, "_stage", None) is not stage) or (
            delivery.destination is not None and delivery.destination._stage is not stage
        ):
            delivery.receivers = ()
            continue
        receivers: list[Action] = []
        for handler in tuple(stage._message_handlers.get(delivery.message, ())):
            if not stage.running:
                break
            if delivery.destination is not None and handler.actor is not delivery.destination:
                continue
            root = _trigger(stage, handler, delivery=delivery)
            if root is not None:
                receivers.append(root)
        delivery.receivers = tuple(receivers)


def _step(stage: Stage) -> None:
    # Snapshot the entire tree: admissions during this phase wait until the next one.
    for action in _actions(stage):
        if not stage.running or stage.paused:
            break
        if action.done:
            continue
        state = action._state
        at = stage.time
        if isinstance(state, _Queued):
            predecessor = action._after
            if predecessor is not None:
                if not predecessor.done:
                    continue
                if predecessor.cancelled:
                    _cancel(stage, action)
                    continue
                if predecessor.exception is not None:
                    raise predecessor.exception
                completed = predecessor._state
                assert isinstance(completed, _Completion)
                at = max(state.admitted_at, completed.at)
            action._state = _Fiber(state.work)
            action._after = None
        fiber = action._state
        if not isinstance(fiber, _Fiber):
            continue
        try:
            completed_at = _advance(stage, action, fiber, at)
            if completed_at is not None and not action.done:
                _finish(action, _Outcome.SUCCESS, completed_at)
        except ActionCancelled:
            _cancel(stage, action)
        except BaseException as error:
            error.add_note(f"Plocks action on {type(action._actor).__name__}")
            try:
                _finish(action, error, stage.time)
            except BaseException as cleanup:  # noqa: BLE001 -- preserve the primary action failure
                error.add_note(f"Action cleanup also failed: {cleanup!r}")
            raise


def _ready(stage: Stage, root: Action, request: _Request, at: float) -> float | None:
    deadline = _deadline(request)
    if deadline is not None:
        if isinstance(request, _Glide):
            _sample_glide(request, stage.time)
        if stage.time + 1e-12 < deadline:
            return None
        _freeze(request, deadline, cancel=False)
        return deadline
    if isinstance(request, _JoinDelivery):
        receivers = request.delivery.receivers
        if request.wait_receivers and receivers is not None:
            for receiver in receivers:
                if not receiver.done and _depends_on(receiver, root):
                    raise StageError("A message receiver cannot wait for its sending ancestor")
        return (
            stage.time
            if receivers is not None
            and (not request.wait_receivers or all(r.done for r in receivers))
            else None
        )
    if isinstance(request, (_AwaitAction, _AwaitAll)):
        actions = (request.action,) if isinstance(request, _AwaitAction) else request.actions
        if isinstance(request, _AwaitAll) and any(a.cancelled for a in actions):
            _cancel(stage, root)
            return None
        for action in actions:
            if action._stage is not stage:
                raise StageError("Await actions from the same stage")
            if not action.done and _depends_on(action, root):
                raise StageError("An action cannot wait for itself or its ancestor")
        return stage.time if all(a.done for a in actions) else None
    if isinstance(request, _SoundWait):
        return stage.time if request.voice.finished else None
    if isinstance(request, _During):
        _advance(stage, root, request.foreground, at)
        if request.foreground.coroutine is None:
            _close_fiber(stage, request.background)
            return stage.time
        _advance(stage, root, request.background, at)
        return None
    return at


def _advance(stage: Stage, root: Action, fiber: _Fiber, at: float) -> float | None:
    for _ in range(256):
        if root.done or not stage.running or stage.paused:
            return None
        request = fiber.waiting
        response: object = None
        if request is not None:
            ready = _ready(stage, root, request, at)
            if ready is None:
                return None
            at = ready
            if isinstance(request, _Context):
                response = (stage, root, fiber, at)
        fiber.waiting = None
        coroutine = fiber.coroutine
        if coroutine is None:
            return None
        before = _actions(stage)
        try:
            yielded = coroutine.send(response)
        except StopIteration:
            fiber.coroutine = None
            return at
        finally:
            _adopt(stage, fiber, before)
            if root.done:
                _close_fiber(stage, fiber)
        if root.done:
            _freeze(
                yielded
                if isinstance(yielded, (_Glide, _ImageRun, _PoseRun, _BubbleRun, _SoundWait))
                else None,
                stage.time,
                cancel=True,
            )
            return None
        if not isinstance(
            yielded,
            (
                _Context,
                _AwaitAction,
                _AwaitAll,
                _Delay,
                _Glide,
                _ForceRun,
                _TorqueRun,
                _ImageRun,
                _PoseRun,
                _During,
                _JoinDelivery,
                _SoundWait,
                _BubbleRun,
            ),
        ):
            raise StageError("Scripts must await Plocks operations, not asyncio or external I/O")
        fiber.waiting = yielded
        if isinstance(yielded, _During) and _count(stage) > 128:
            raise StageError("During exceeded the 128 live-fiber limit")

    return None


def _stop_actor(actor: Sprite | Puppet, action: Action | None) -> None:
    stage = actor._stage
    if action is not None and action._actor is not actor:
        raise StageError("stop(action) requires this actor's action; use action.cancel() otherwise")
    if stage is None:
        return
    for root in tuple(stage._actions):
        owned = any(a._actor is actor and (action is None or a is action) for a in _walk(root))
        operating = action is None and any(
            isinstance(f.waiting, (_Glide, _ImageRun, _PoseRun, _BubbleRun))
            and f.waiting.actor is actor
            for f in _fibers(root)
        )
        if owned or operating:
            _cancel(stage, root)


def _depends_on(action: Action, target: Action) -> bool:
    pending = [action]
    seen: set[Action] = set()
    while pending:
        current = pending.pop()
        if current is target:
            return True
        if current in seen or current.done:
            continue
        seen.add(current)
        if current._after is not None:
            pending.append(current._after)
        if isinstance(current._state, _Fiber):
            for fiber in _branches(current._state):
                request = fiber.waiting
                if isinstance(request, _AwaitAction):
                    pending.append(request.action)
                elif isinstance(request, _AwaitAll):
                    pending.extend(request.actions)
                elif (
                    isinstance(request, _JoinDelivery)
                    and request.wait_receivers
                    and request.delivery.receivers is not None
                ):
                    pending.extend(request.delivery.receivers)
    return False
