"""Bounded stage-owned coroutine trees; traversal scratch never becomes a scheduler cache."""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Iterator
from dataclasses import dataclass
from enum import Enum
from types import CoroutineType
from typing import TYPE_CHECKING

from ._operations import (
    _BubbleRun,
    _Context,
    _CostumeRun,
    _deadline,
    _Delay,
    _During,
    _freeze,
    _Glide,
    _Join,
    _PoseRun,
    _Request,
    _sample_glide,
    _SoundWait,
)
from .errors import StageError

if TYPE_CHECKING:
    from .puppets import Puppet
    from .sprites import Sprite
    from .stage import Stage


class WhenBusy(Enum):
    """Ignore repeated triggers, or cancel the previous invocation and restart."""

    IGNORE = "ignore"
    RESTART = "restart"


@dataclass(eq=False, slots=True)
class _Handler:
    start: Callable[[object], Coroutine[object, object, None] | None]
    actor: Sprite | Puppet | None
    block: object | None
    when_busy: WhenBusy


@dataclass(eq=False, slots=True)
class _Fiber:
    coroutine: Coroutine[object, object, None] | None
    waiting: _Request | None = None


@dataclass(eq=False, slots=True)
class _Run:
    actor: Sprite | Puppet | None
    block: object | None
    handler: _Handler | None
    fiber: _Fiber


def _fibers(fiber: _Fiber) -> Iterator[_Fiber]:
    yield fiber
    if isinstance(fiber.waiting, _During):
        yield from _fibers(fiber.waiting.foreground)
        yield from _fibers(fiber.waiting.background)


def _count(stage: Stage) -> int:
    return sum(f.coroutine is not None for r in stage._runs for f in _fibers(r.fiber))


def _admit(
    stage: Stage,
    coroutine: Coroutine[object, object, None],
    actor: Sprite | Puppet | None,
    block: object | None,
    handler: _Handler | None = None,
) -> _Run:
    if stage._state == "closed" or _count(stage) >= 128:
        coroutine.close()
        raise StageError(
            f"Cannot start {block or handler}: stage closed or 128-fiber limit reached"
        )
    root = _Run(actor, block, handler, _Fiber(coroutine))
    stage._runs.append(root)
    return root


def _close_fiber(stage: Stage, fiber: _Fiber) -> None:
    request = fiber.waiting
    errors: list[BaseException] = []
    if isinstance(request, _During):
        for child in (request.background, request.foreground):
            try:
                _close_fiber(stage, child)
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


def _cancel(stage: Stage, root: _Run) -> None:
    if root in stage._runs:
        stage._runs.remove(root)
    _close_fiber(stage, root.fiber)


def _trigger(stage: Stage, handler: _Handler, data: object = None) -> _Run | None:
    if not stage.running:
        return None
    if handler.actor is not None and handler.actor._stage is not stage:
        return None
    busy = [root for root in stage._runs if root.handler is handler]
    if busy and handler.when_busy is WhenBusy.IGNORE:
        return None
    for root in busy:
        _cancel(stage, root)
    result = handler.start(data)
    return None if result is None else _admit(stage, result, handler.actor, handler.block, handler)


def _conflicts(
    actor: Sprite | Puppet,
    x: bool,
    y: bool,
    current: _Run | None = None,
    *,
    visual: bool = False,
    bubble: bool = False,
) -> None:
    stage = actor._stage
    if stage is None:
        return
    for root in tuple(stage._runs):
        for fiber in tuple(_fibers(root.fiber)):
            request = fiber.waiting
            if (
                not isinstance(request, (_Glide, _CostumeRun, _PoseRun, _BubbleRun))
                or request.actor is not actor
            ):
                continue
            deadline = _deadline(request)
            if deadline is not None and deadline <= stage.time + 1e-12:
                continue
            overlap = (
                (bubble and isinstance(request, _BubbleRun))
                or (visual and isinstance(request, (_CostumeRun, _PoseRun)))
                or (
                    isinstance(request, _Glide)
                    and ((x and request.x is not None) or (y and request.y is not None))
                )
            )
            if overlap:
                if root is current:
                    raise StageError("During branches cannot control the same property")
                _cancel(stage, root)
                break


def _detach(stage: Stage, actor: Sprite | Puppet) -> None:
    affected = [
        root
        for root in stage._runs
        if root.actor is actor
        or any(
            isinstance(f.waiting, (_Glide, _CostumeRun, _PoseRun, _BubbleRun))
            and f.waiting.actor is actor
            for f in _fibers(root.fiber)
        )
    ]
    # Freeze while the association is still valid; reject re-admission during cleanup.
    for root in affected:
        for fiber in _fibers(root.fiber):
            _freeze(fiber.waiting, stage.time, cancel=True)
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
    if errors:
        raise errors[0]


def _sample(stage: Stage) -> None:
    for root in tuple(stage._runs):
        for fiber in _fibers(root.fiber):
            if isinstance(fiber.waiting, _Glide):
                _sample_glide(fiber.waiting, stage.time)


def _deliver(stage: Stage) -> None:
    pending = tuple(stage._messages)
    stage._messages.clear()
    for delivery in pending:
        receivers: list[_Run] = []
        for handler in tuple(stage._message_handlers.get(delivery.message, ())):
            if not stage.running:
                break
            root = _trigger(stage, handler, delivery.data)
            if root is not None:
                receivers.append(root)
        delivery.receivers = tuple(receivers)


def _step(stage: Stage) -> None:
    for root in tuple(stage._runs):
        if not stage.running or stage.paused:
            break
        if root not in stage._runs:
            continue
        try:
            _advance(stage, root, root.fiber, stage.time)
        except BaseException as error:
            error.add_note(f"Plocks behavior: {root.block or root.handler}")
            raise
        if root.fiber.coroutine is None or root not in stage._runs:
            _cancel(stage, root)


def _ready(stage: Stage, root: _Run, request: _Request, at: float) -> float | None:
    deadline = _deadline(request)
    if deadline is not None:
        if isinstance(request, _Glide):
            _sample_glide(request, stage.time)
        if stage.time + 1e-12 < deadline:
            return None
        _freeze(request, deadline, cancel=False)
        return deadline
    if isinstance(request, _Join):
        receivers = request.delivery.receivers
        return (
            stage.time
            if receivers is not None and all(r not in stage._runs for r in receivers)
            else None
        )
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


def _advance(stage: Stage, root: _Run, fiber: _Fiber, at: float) -> None:
    for _ in range(256):
        if root not in stage._runs or not stage.running or stage.paused:
            return
        request = fiber.waiting
        response: object = None
        if request is not None:
            ready = _ready(stage, root, request, at)
            if ready is None:
                return
            at = ready
            if isinstance(request, _Context):
                response = (stage, root, fiber, at)
        fiber.waiting = None
        coroutine = fiber.coroutine
        if coroutine is None:
            return
        try:
            yielded = coroutine.send(response)
        except StopIteration:
            fiber.coroutine = None
            return
        if not isinstance(
            yielded,
            (
                _Context,
                _Delay,
                _Glide,
                _CostumeRun,
                _PoseRun,
                _During,
                _Join,
                _SoundWait,
                _BubbleRun,
            ),
        ):
            raise StageError("Scripts must await Plocks operations, not asyncio or external I/O")
        fiber.waiting = yielded
        if isinstance(yielded, _During) and _count(stage) > 128:
            raise StageError("During exceeded the 128 live-fiber limit")
