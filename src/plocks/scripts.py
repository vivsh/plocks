"""Reusable behavior definitions; targets bind only when execution is admitted."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Generic, Self, TypeVar, cast, overload

from typing_extensions import deprecated

from ._commands import (
    Actor,
    _BounceOnEdge,
    _ClearBubble,
    _Command,
    _DuringPlan,
    _FollowPath,
    _GlideBy,
    _GlideTo,
    _GoToRandom,
    _Images,
    _Move,
    _MoveTo,
    _Plan,
    _PlaySound,
    _PointTowards,
    _Poses,
    _Say,
    _Send,
    _SetImage,
    _SetPartImage,
    _SetPose,
    _Think,
    _TurnLeft,
    _TurnRight,
    _Wait,
    _When,
)
from .audio import Sound
from .conditions import Condition, _validate
from .geometry import Bounds, Point, _integer
from .imaging import ImageSource
from .messages import Message
from .motion import Ease
from .puppets import Puppet
from .rigging import Pose
from .sprites import Sprite

_T = TypeVar("_T", bound=Actor)
_D = TypeVar("_D")


class Script(Generic[_T]):  # noqa: UP046 -- explicit invariance protects editable definitions and payloads
    """Record a reusable sequence without executing it or binding an actor.

    Script() works on either actor. Script(Sprite) adds images; Script(Puppet)
    adds poses. act() snapshots the script; edits affect future executions only.
    All methods return this builder. Durations use simulated seconds.
    """

    __slots__ = ("_commands", "_target_type", "_times")

    @overload
    def __init__(self: Script[Actor]) -> None: ...
    @overload
    def __init__(self: Script[Sprite], target_type: type[Sprite]) -> None: ...
    @overload
    def __init__(self: Script[Puppet], target_type: type[Puppet]) -> None: ...
    def __init__(self, target_type: type[Sprite | Puppet] | None = None) -> None:
        if target_type is not None and target_type not in (Sprite, Puppet):
            raise TypeError("Use Script(), Script(Sprite), or Script(Puppet)")
        self._target_type: type[Sprite | Puppet] | None = target_type
        self._times: int | None = 1
        self._commands: list[_Command[_T]] = []

    def repeat(self, times: int | None = None) -> Self:
        """Repeat this entire sequence; omit times for indefinite repetition."""
        if times is not None:
            _integer(times, "times", minimum=0)
        self._times = times
        return self

    def call(self, script: Script[_T] | Script[Actor]) -> Self:
        """Append a snapshot of another Script; run it on the current target."""
        self._commands.append(_nested(script, self._target_type))
        _check(_Plan(self._target_type, tuple(self._commands), 1))
        return self

    def during(
        self, foreground: Script[_T] | Script[Actor], *, meanwhile: Script[_T] | Script[Actor]
    ) -> Self:
        """Run both branches; foreground completion cancels unfinished background."""
        self._commands.append(
            _DuringPlan(
                _nested(foreground, self._target_type),
                background=_nested(meanwhile, self._target_type),
            )
        )
        _check(_Plan(self._target_type, tuple(self._commands), 1))
        return self

    def when(
        self,
        condition: Condition,
        *,
        then: Script[_T] | Script[Actor],
        either: Script[_T] | Script[Actor] | None = None,
    ) -> Self:
        """Test once when reached; run then or either and continue afterward."""
        _validate(condition)
        self._commands.append(
            _When(
                condition,
                _nested(then, self._target_type),
                None if either is None else _nested(either, self._target_type),
            )
        )
        _check(_Plan(self._target_type, tuple(self._commands), 1))
        return self

    @overload
    def broadcast(
        self, message: Message[None], *, to: Actor | None = None, wait: bool = False
    ) -> Self: ...
    @overload
    def broadcast(
        self, message: Message[_D], data: _D, *, to: Actor | None = None, wait: bool = False
    ) -> Self: ...
    def broadcast(
        self,
        message: Message[_D],
        data: _D | None = None,
        *,
        to: Actor | None = None,
        wait: bool = False,
    ) -> Self:
        """Broadcast on arrival from the executing actor; wait=True joins accepted receivers.

        Default delivery broadcasts within the stage; to restricts the receiver.
        Data is captured by reference now. This method schedules nothing.
        """
        _message_arguments(message, to, wait)
        self._commands.append(_Send(cast(Message[object], message), data, to, wait))
        return self

    def move(self, steps: float) -> Self:
        """Move along direction in logical pixels when reached. Records a command; schedules nothing."""
        self._commands.append(_Move(steps))
        return self

    def move_to(self, *, x: float | None = None, y: float | None = None) -> Self:
        """Set supplied world coordinates when reached; omitted axes stay unchanged. Records a command; schedules nothing."""
        self._commands.append(_MoveTo(x=x, y=y))
        return self

    def glide_to(
        self,
        *,
        x: float | None = None,
        y: float | None = None,
        seconds: float,
        easing: Ease = Ease.LINEAR,
    ) -> Self:
        """Glide to world coordinates over simulated seconds; omitted axes stay free. Records a command; schedules nothing."""
        self._commands.append(_GlideTo(x=x, y=y, seconds=seconds, easing=easing))
        return self

    def follow_path(self, points: Iterable[Point], *, speed: float = 100) -> Self:
        """Record immutable world waypoints at pixels/second; no route is recomputed."""
        self._commands.append(_FollowPath(points, speed=speed))
        return self

    def glide_by(
        self,
        *,
        x: float | None = None,
        y: float | None = None,
        seconds: float,
        easing: Ease = Ease.LINEAR,
    ) -> Self:
        """Glide by logical pixels, capturing the starting position when execution begins. Records a command; schedules nothing."""
        self._commands.append(_GlideBy(x=x, y=y, seconds=seconds, easing=easing))
        return self

    def wait(self, seconds: float) -> Self:
        """Wait simulated seconds; pause freezes progress and zero yields one tick. Records a command; schedules nothing."""
        self._commands.append(_Wait(seconds))
        return self

    def turn_left(self, degrees: float) -> Self:
        """Turn counterclockwise by degrees when reached. Records a command; schedules nothing."""
        self._commands.append(_TurnLeft(degrees))
        return self

    def turn_right(self, degrees: float) -> Self:
        """Turn clockwise by degrees when reached. Records a command; schedules nothing."""
        self._commands.append(_TurnRight(degrees))
        return self

    def point_towards(self, target: Point | Actor) -> Self:
        """Face a world point or the target actor position sampled when reached. Records a command; schedules nothing."""
        self._commands.append(_PointTowards(target))
        return self

    def go_to_random(self, bounds: Bounds | None = None) -> Self:
        """Choose an anchor position uniformly in bounds, or the visible world. Records a command; schedules nothing."""
        self._commands.append(_GoToRandom(bounds))
        return self

    def bounce_on_edge(self, bounds: Bounds | None = None) -> Self:
        """Fit within bounds and reflect outward motion; oversized actors raise ValueError. Records a command; schedules nothing."""
        self._commands.append(_BounceOnEdge(bounds))
        return self

    def say(self, text: str, *, seconds: float | None = None) -> Self:
        """Show speech captured now; omit seconds to persist, or wait then clear this occurrence. Records a command; schedules nothing."""
        self._commands.append(_Say(text, seconds=seconds))
        return self

    def think(self, text: str, *, seconds: float | None = None) -> Self:
        """Show thought captured now; timed dialogue waits using the simulation clock. Records a command; schedules nothing."""
        self._commands.append(_Think(text, seconds=seconds))
        return self

    def clear_bubble(self) -> Self:
        """Clear speech or thought when reached, interrupting any timed bubble writer. Records a command; schedules nothing."""
        self._commands.append(_ClearBubble())
        return self

    def play_sound(self, sound: Sound, *, volume: float = 1, wait: bool = True) -> Self:
        """Play one sound occurrence; by default wait for its channel to finish. Records a command; schedules nothing."""
        self._commands.append(_PlaySound(sound, volume=volume, wait=wait))
        return self

    def set_image(self: Script[Sprite], image: ImageSource) -> Script[Sprite]:
        """Snapshot an image now and display it when reached. Records a command; schedules nothing."""
        self._commands.append(_SetImage(image))
        return self

    @overload
    def images(
        self: Script[Sprite], frames: Iterable[ImageSource], *, fps: float
    ) -> Script[Sprite]: ...
    @overload
    def images(
        self: Script[Sprite], frames: Iterable[ImageSource], *, durations: Iterable[float]
    ) -> Script[Sprite]: ...
    def images(
        self: Script[Sprite],
        frames: Iterable[ImageSource],
        *,
        fps: float | None = None,
        durations: Iterable[float] | None = None,
    ) -> Script[Sprite]:
        """Play one frame pass using fps or per-frame durations in simulation seconds.

        Supply exactly one timing form. Every frame, including the final one,
        holds for its full positive duration. Sources/timings are snapshotted now.
        """
        self._commands.append(_Images(frames, fps=fps, durations=durations))
        return self

    def set_pose(self: Script[Puppet], pose: Pose) -> Script[Puppet]:
        """Set a complete pose belonging to this Puppet skeleton. Records a command; schedules nothing."""
        self._commands.append(_SetPose(pose))
        return self

    def poses(self: Script[Puppet], poses: Iterable[Pose], *, fps: float) -> Script[Puppet]:
        """Interpolate adjacent poses at fps; repeat the first pose to author a closing transition. Records a command; schedules nothing."""
        self._commands.append(_Poses(poses, fps=fps))
        return self

    def set_part_image(self: Script[Puppet], joint: str, image: ImageSource) -> Script[Puppet]:
        """Replace an existing attachment without changing topology or interrupting pose motion. Records a command; schedules nothing."""
        self._commands.append(_SetPartImage(joint, image))
        return self

    @deprecated("set_costume is deprecated; use set_image")
    def set_costume(self: Script[Sprite], costume: ImageSource) -> Script[Sprite]:
        """Deprecated alias for set_image; records the same command."""
        return self.set_image(costume)

    @overload
    @deprecated("costumes is deprecated; use images")
    def costumes(
        self: Script[Sprite], frames: Iterable[ImageSource], *, fps: float
    ) -> Script[Sprite]: ...
    @overload
    @deprecated("costumes is deprecated; use images")
    def costumes(
        self: Script[Sprite], frames: Iterable[ImageSource], *, durations: Iterable[float]
    ) -> Script[Sprite]: ...
    @deprecated("costumes is deprecated; use images")
    def costumes(
        self: Script[Sprite],
        frames: Iterable[ImageSource],
        *,
        fps: float | None = None,
        durations: Iterable[float] | None = None,
    ) -> Script[Sprite]:
        """Deprecated alias for images; records the same timed pass."""
        if fps is not None and durations is None:
            return self.images(frames, fps=fps)
        if durations is not None and fps is None:
            return self.images(frames, durations=durations)
        raise ValueError("Supply exactly one of fps or durations")

    @deprecated("set_part_costume is deprecated; use set_part_image")
    def set_part_costume(self: Script[Puppet], joint: str, costume: ImageSource) -> Script[Puppet]:
        """Deprecated alias for set_part_image; records the same attachment edit."""
        return self.set_part_image(joint, costume)


def _message_arguments(message: object, target: object, wait: bool) -> None:
    if not isinstance(message, Message):
        raise TypeError("Use a Message token, not a string")
    if target is not None and not isinstance(target, (Sprite, Puppet)):
        raise TypeError("Message destination must be an actor")
    if not isinstance(wait, bool):
        raise TypeError("wait must be bool")


def _nested[T: Actor](
    script: Script[T] | Script[Actor], target: type[Sprite | Puppet] | None
) -> _Command[T]:
    if not isinstance(script, Script):
        raise TypeError("call/composition requires a Script, not a Python function")
    if script._target_type is not None and script._target_type is not target:
        raise TypeError("Nested Script requires an incompatible actor type")
    recipe = cast(Script[T], script)
    plan: _Plan[T] = _Plan[T](recipe._target_type, tuple(recipe._commands), recipe._times)
    _check(plan)
    return plan


def _check[T: Actor](plan: _Command[T], actor: T | None = None) -> None:
    pending = [(plan, 0)]
    count = 0
    while pending:
        command, depth = pending.pop()
        count += 1
        if count > 4096 or depth > 32:
            raise ValueError("Scripts allow 4096 commands and 32 nesting levels")
        if isinstance(command, _Plan):
            if command.times is None and not command.commands:
                raise ValueError("An indefinite Script must contain commands")
            if (
                actor is not None
                and command.target_type is not None
                and type(cast(Actor, actor)) is not command.target_type
            ):
                raise TypeError("Script target type is incompatible with this actor")
            pending.extend((child, depth + 1) for child in command.commands)
        elif isinstance(command, _DuringPlan):
            pending.extend(((command.foreground, depth + 1), (command.background, depth + 1)))
        elif isinstance(command, _When):
            _validate(command.condition)
            pending.append((command.then, depth + 1))
            if command.either is not None:
                pending.append((command.either, depth + 1))
        if actor is None:
            continue
        if isinstance(command, (_SetImage, _Images)) and not isinstance(actor, Sprite):
            raise TypeError("Image Script requires a Sprite")
        if isinstance(command, (_SetPose, _Poses, _SetPartImage)):
            if not isinstance(actor, Puppet):
                raise TypeError("Pose/part Script requires a Puppet")
            if isinstance(command, (_SetPose, _Poses)):
                pose = command.pose if isinstance(command, _SetPose) else command.poses[0]
                if pose.skeleton is not actor.skeleton:
                    raise ValueError("Script pose belongs to another skeleton")
            elif command.joint not in actor.parts:
                raise KeyError(command.joint)


def _snapshot[T: Actor](script: Script[T] | Script[Actor], actor: T) -> _Command[T]:
    if not isinstance(script, Script):
        raise TypeError("act requires a Script")
    recipe = cast(Script[T], script)
    plan: _Plan[T] = _Plan[T](recipe._target_type, tuple(recipe._commands), recipe._times)
    _check(plan, actor)
    return plan
