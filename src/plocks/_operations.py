"""Private coroutine requests; timing belongs to one waiting fiber."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from .geometry import Point, _number
from .motion import Ease, _ease

if TYPE_CHECKING:
    from ._commands import _Costumes, _Poses, _Say, _Think
    from ._scripts import _Fiber
    from .actions import Action
    from .audio import Voice
    from .imaging import Costume
    from .messages import Message
    from .physics import Body
    from .puppets import Puppet
    from .rigging import Pose
    from .sprites import Sprite
    from .stage import Stage


@dataclass(frozen=True, slots=True)
class _AwaitAction:
    action: Action


@dataclass(frozen=True, slots=True)
class _AwaitAll:
    actions: tuple[Action, ...]


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
    _ForceRun
    | _TorqueRun
    | _AwaitAction
    | _AwaitAll
    | _Context
    | _Delay
    | _Glide
    | _CostumeRun
    | _PoseRun
    | _During
    | _JoinDelivery
    | _SoundWait
    | _BubbleRun
)
type _ExecutionContext = tuple[Stage, Action, _Fiber, float]


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
    from .physics import Body, BodyType

    if isinstance(actor._transform, Body) and actor.body_type is not BodyType.KINEMATIC:
        from .errors import PhysicsError

        raise PhysicsError(
            "Glides require a kinematic or nonphysical actor; use body velocity or impulses"
        )
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
    from .motion import _set_position
    from .physics import Body, _native

    if isinstance(operation.actor._transform, Body) and progress < 1:
        return
    x, y = operation.actor.position
    if operation.x is not None:
        start, end = operation.x
        x = end if progress == 1 else (1 - progress) * start + progress * end
    if operation.y is not None:
        start, end = operation.y
        y = end if progress == 1 else (1 - progress) * start + progress * end
    _set_position(operation.actor, (x, y))
    if isinstance(operation.actor._transform, Body):
        native = _native(operation.actor._transform)
        vx, vy = native.velocity
        native.velocity = (
            0 if operation.x is not None else vx,
            0 if operation.y is not None else vy,
        )


@dataclass(frozen=True, slots=True)
class _BubbleRun:
    actor: Sprite | Puppet
    definition: _Say | _Think
    deadline: float


async def _speak(actor: Sprite | Puppet, definition: _Say | _Think) -> None:
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
    definition: _Costumes
    started: float


@dataclass(frozen=True, slots=True)
class _PoseRun:
    actor: Puppet
    definition: _Poses
    started: float


@dataclass(slots=True)
class _During:
    foreground: _Fiber
    background: _Fiber


@dataclass(eq=False, slots=True)
class _Delivery:
    message: Message[object]
    source: Stage | Sprite | Puppet
    data: object
    destination: Sprite | Puppet | None
    receivers: tuple[Action, ...] | None = None


@dataclass(frozen=True, slots=True)
class _JoinDelivery:
    delivery: _Delivery
    wait_receivers: bool


@dataclass(frozen=True, slots=True)
class _SoundWait:
    voice: Voice


def _sample_costume(operation: _CostumeRun, now: float) -> Costume:
    elapsed = max(0.0, now - operation.started)
    end = 0.0
    for frame, duration in zip(operation.definition.frames, operation.definition.durations):
        end += duration
        if elapsed + 1e-12 < end:
            return frame
    return operation.definition.frames[-1]


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
    if isinstance(request, (_Glide, _ForceRun, _TorqueRun)):
        return request.started + request.seconds
    if isinstance(request, _CostumeRun):
        return request.started + sum(request.definition.durations)
    if isinstance(request, _PoseRun):
        return request.started + (len(request.definition.poses) - 1) / request.definition.fps
    return None


def _freeze(request: _Request | None, now: float, *, cancel: bool) -> None:
    if isinstance(request, _Glide):
        from .physics import Body, _native

        if isinstance(request.actor._transform, Body):
            native = _native(request.actor._transform)
            vx, vy = native.velocity
            native.velocity = (
                0 if request.x is not None else vx,
                0 if request.y is not None else vy,
            )
    if isinstance(request, _BubbleRun) and request.actor._bubble is request:
        request.actor._bubble = None
    elif isinstance(request, _CostumeRun) and request.actor._visual is request:
        request.actor._visual = _sample_costume(request, now)
    elif isinstance(request, _PoseRun) and request.actor._pose is request:
        request.actor._pose = _sample_pose(request, now)
    elif isinstance(request, _SoundWait) and cancel:
        request.voice.stop()


@dataclass(frozen=True, slots=True)
class _ForceRun:
    body: Body
    vector: Point
    point: Point | None
    started: float
    seconds: float


@dataclass(frozen=True, slots=True)
class _TorqueRun:
    body: Body
    amount: float
    started: float
    seconds: float
