"""Private coroutine requests; timing belongs to one waiting fiber."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from .geometry import _number
from .motion import Ease, _ease

if TYPE_CHECKING:
    from ._scripts import _Fiber, _Run
    from .audio import Voice
    from .blocks import Costumes, Poses, Say, Think
    from .imaging import Costume
    from .messages import Message, Signal
    from .puppets import Puppet
    from .rigging import Pose
    from .sprites import Sprite
    from .stage import Stage


@dataclass(frozen=True, slots=True)
class _Context:
    pass


@dataclass(frozen=True, slots=True)
class _Delay:
    deadline: float


@dataclass(frozen=True, slots=True)
class _Glide:
    actor: Sprite | Puppet
    x: tuple[float, float] | None
    y: tuple[float, float] | None
    started: float
    seconds: float
    easing: Ease


type _Request = (
    _Context | _Delay | _Glide | _CostumeRun | _PoseRun | _During | _Join | _SoundWait | _BubbleRun
)
type _ExecutionContext = tuple[Stage, _Run, _Fiber, float]


def _request(request: _Request) -> Generator[object, object, object]:
    return (yield request)


# types.coroutine makes this small generator a native-coroutine awaitable.
from types import coroutine

_suspend = coroutine(_request)


async def _context() -> _ExecutionContext:
    return cast("_ExecutionContext", await _suspend(_Context()))


async def _wait(stage: Stage, seconds: float) -> None:
    seconds = _number(seconds, "seconds", minimum=0)
    owner, _, _, at = await _context()
    if owner is not stage:
        from .errors import StageError

        raise StageError("Wait must use the executing stage")
    deadline = at + seconds if seconds else stage.time + 1 / stage.tick_rate
    await _suspend(_Delay(_number(deadline, "wait deadline")))


async def _glide(
    actor: Sprite | Puppet,
    x: float | None,
    y: float | None,
    seconds: float,
    easing: Ease,
    *,
    relative: bool,
) -> None:
    from ._scripts import _conflicts
    from .errors import StageError

    seconds = _number(seconds, "seconds", minimum=0)
    if x is None and y is None:
        raise ValueError("Supply x, y, or both")
    if x is not None:
        x = _number(x, "x")
    if y is not None:
        y = _number(y, "y")
    stage, root, _, at = await _context()
    if actor._stage is not stage:
        raise StageError("The actor must belong to the executing stage")
    _number(at + seconds, "glide deadline")
    end_x = None if x is None else _number(x + (actor.x if relative else 0), "destination x")
    end_y = None if y is None else _number(y + (actor.y if relative else 0), "destination y")
    _conflicts(actor, x is not None, y is not None, root)
    # Cancellation cleanup may alter the starting position.
    if relative:
        end_x = None if x is None else _number(actor.x + x, "destination x")
        end_y = None if y is None else _number(actor.y + y, "destination y")
    operation = _Glide(
        actor,
        None if end_x is None else (actor.x, end_x),
        None if end_y is None else (actor.y, end_y),
        at,
        seconds,
        easing,
    )
    if seconds == 0:
        _sample_glide(operation, stage.time)
        await _suspend(_Delay(stage.time + 1 / stage.tick_rate))
    else:
        await _suspend(operation)


def _sample_glide(operation: _Glide, now: float) -> None:
    progress = (
        1.0
        if not operation.seconds or now + 1e-12 >= operation.started + operation.seconds
        else min(1.0, max(0.0, (now - operation.started) / operation.seconds))
    )
    progress = _ease(progress, operation.easing)
    if operation.x is not None:
        start, end = operation.x
        operation.actor._x = end if progress == 1 else (1 - progress) * start + progress * end
    if operation.y is not None:
        start, end = operation.y
        operation.actor._y = end if progress == 1 else (1 - progress) * start + progress * end


@dataclass(frozen=True, slots=True)
class _BubbleRun:
    actor: Sprite | Puppet
    definition: Say | Think
    deadline: float


async def _speak(actor: Sprite | Puppet, definition: Say | Think) -> None:
    from ._scripts import _conflicts
    from .errors import StageError

    stage, root, _, at = await _context()
    if actor._stage is not stage:
        raise StageError("Bubble blocks require membership in the executing stage")
    seconds = definition.seconds
    deadline = (
        None
        if seconds is None
        else _number(
            at + seconds if seconds else stage.time + 1 / stage.tick_rate, "bubble deadline"
        )
    )
    if not definition.text.strip() or deadline is None:
        _conflicts(actor, False, False, bubble=True)
        actor._bubble = definition if deadline is None and definition.text.strip() else None
        if deadline is not None:
            await _suspend(_Delay(deadline))
        return
    _conflicts(actor, False, False, root, bubble=True)
    if actor._stage is not stage:
        raise StageError("Bubble target was detached during cancellation cleanup")
    operation = _BubbleRun(actor, definition, deadline)
    actor._bubble = operation
    await _suspend(operation)


@dataclass(frozen=True, slots=True)
class _CostumeRun:
    actor: Sprite
    definition: Costumes
    started: float


@dataclass(frozen=True, slots=True)
class _PoseRun:
    actor: Puppet
    definition: Poses
    started: float


@dataclass(slots=True)
class _During:
    foreground: _Fiber
    background: _Fiber


@dataclass(eq=False, slots=True)
class _Delivery:
    message: Signal | Message[object]
    data: object
    receivers: tuple[_Run, ...] | None = None


@dataclass(frozen=True, slots=True)
class _Join:
    delivery: _Delivery


@dataclass(frozen=True, slots=True)
class _SoundWait:
    voice: Voice


def _sample_costume(operation: _CostumeRun, now: float) -> Costume:
    frames = operation.definition.frames
    if now + 1e-12 >= operation.started + len(frames) / operation.definition.fps:
        return frames[-1]
    index = min(
        len(frames) - 1, max(0, int((now - operation.started) * operation.definition.fps + 1e-10))
    )
    return frames[index]


def _sample_pose(operation: _PoseRun, now: float) -> Pose:
    from .rigging import Pose

    frames = operation.definition.poses
    progress = max(0.0, (now - operation.started) * operation.definition.fps)
    if progress + 1e-10 >= len(frames) - 1:
        return frames[-1]
    index = int(progress)
    fraction = progress - index
    first, second = frames[index], frames[index + 1]
    angles: dict[str, float] = {}
    for name, start in first.angles.items():
        delta = (second.angles[name] - start + 180) % 360 - 180
        if delta == -180:
            delta = 180
        angles[name] = start + delta * fraction
    return Pose(first.skeleton, angles)


def _deadline(request: _Request) -> float | None:
    if isinstance(request, (_Delay, _BubbleRun)):
        return request.deadline
    if isinstance(request, _Glide):
        return request.started + request.seconds
    if isinstance(request, _CostumeRun):
        return request.started + len(request.definition.frames) / request.definition.fps
    if isinstance(request, _PoseRun):
        return request.started + (len(request.definition.poses) - 1) / request.definition.fps
    return None


def _freeze(request: _Request | None, now: float, *, cancel: bool) -> None:
    if isinstance(request, _BubbleRun) and request.actor._bubble is request:
        request.actor._bubble = None
    elif isinstance(request, _CostumeRun) and request.actor._visual is request:
        request.actor._visual = _sample_costume(request, now)
    elif isinstance(request, _PoseRun) and request.actor._pose is request:
        request.actor._pose = _sample_pose(request, now)
    elif isinstance(request, _SoundWait) and cancel:
        request.voice.stop()
