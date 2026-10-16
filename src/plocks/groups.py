"""Actor-bound recipe builders; each execution takes an immutable snapshot."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Generic, Self, TypeVar

from ._commands import (
    Actor,
    _BounceOnEdge,
    _Call,
    _ClearBubble,
    _Command,
    _Costumes,
    _DuringPlan,
    _GlideBy,
    _GlideTo,
    _GoToRandom,
    _Move,
    _MoveTo,
    _PlaySound,
    _PointTowards,
    _Poses,
    _Repeat,
    _Say,
    _Sequence,
    _SetCostume,
    _SetPartCostume,
    _SetPose,
    _Think,
    _TurnLeft,
    _TurnRight,
    _Wait,
)
from .actions import Action
from .audio import Sound
from .geometry import Bounds, Point, _integer
from .imaging import CostumeSource
from .motion import Ease
from .puppets import Puppet
from .rigging import Pose
from .sprites import Sprite

_T = TypeVar("_T", bound=Actor)


class Group(Generic[_T]):  # noqa: UP046 -- invariant actor binding is contractual
    """Reusable recipe bound to one actor. Recording does not schedule execution.

    Methods append commands in order and return this builder. act() snapshots the
    commands, so later edits affect only future executions. Use an ordinary function
    accepting an actor to reuse a recipe for different actors.
    """

    __slots__ = ("_actor", "_commands", "_times")

    def __init__(self, actor: _T, times: int | None = 1) -> None:
        if times is not None:
            _integer(times, "times", minimum=0)
        self._actor = actor
        self._times = times
        self._commands: list[_Command[_T]] = []

    def act(self, group: Group[_T]) -> Self:
        """Append a snapshot of another recipe for this exact actor."""
        self._commands.append(_snapshot(group, self._actor))
        return self

    def during(self, foreground: Group[_T], *, meanwhile: Group[_T]) -> Self:
        """Append concurrent recipes; foreground completion cancels the background."""
        self._commands.append(
            _DuringPlan(
                _snapshot(foreground, self._actor), background=_snapshot(meanwhile, self._actor)
            )
        )
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

    def call(self, function: Callable[[], None | Action]) -> Self:
        """Run a typed function when reached; wait for its returned Action, if any. Records a command; schedules nothing."""
        self._commands.append(_Call(function))
        return self


class SpriteGroup(Group[Sprite]):
    """A Sprite recipe with costume commands; incompatible with Puppet recipes."""

    __slots__ = ()

    def set_costume(self, costume: CostumeSource) -> Self:
        """Snapshot an image now and display it when reached. Records a command; schedules nothing."""
        self._commands.append(_SetCostume(costume))
        return self

    def costumes(self, frames: Iterable[CostumeSource], *, fps: float) -> Self:
        """Play one costume pass at fps, including the final frame interval. Records a command; schedules nothing."""
        self._commands.append(_Costumes(frames, fps=fps))
        return self


class PuppetGroup(Group[Puppet]):
    """A Puppet recipe with pose and attachment commands."""

    __slots__ = ()

    def set_pose(self, pose: Pose) -> Self:
        """Set a complete pose belonging to this Puppet skeleton. Records a command; schedules nothing."""
        self._commands.append(_SetPose(pose))
        return self

    def poses(self, poses: Iterable[Pose], *, fps: float) -> Self:
        """Interpolate adjacent poses at fps; repeat the first pose to author a closing transition. Records a command; schedules nothing."""
        self._commands.append(_Poses(poses, fps=fps))
        return self

    def set_part_costume(self, joint: str, costume: CostumeSource) -> Self:
        """Replace an existing attachment without changing topology or interrupting pose motion. Records a command; schedules nothing."""
        self._commands.append(_SetPartCostume(joint, costume))
        return self


def _snapshot(group: Group[_T], actor: _T) -> _Command[_T]:  # noqa: UP047 -- shared invariant binding
    if group._actor is not actor:
        raise ValueError(
            "A group belongs to its exact actor; use a function to create another recipe"
        )
    if group._times is None and not group._commands:
        raise ValueError("An infinite group must contain at least one command")
    plan = _Repeat(group._times, _Sequence(tuple(group._commands)))
    pending: list[tuple[_Command[_T], int]] = [(plan, 0)]
    count = 0
    while pending:
        command, depth = pending.pop()
        count += 1
        if count > 4096 or depth > 32:
            raise ValueError("Groups are limited to 4096 commands and 32 nesting levels")
        if isinstance(command, _Sequence):
            pending.extend((child, depth + 1) for child in command.commands)
        elif isinstance(command, _Repeat):
            pending.append((command.command, depth + 1))
        elif isinstance(command, _DuringPlan):
            pending.extend(((command.foreground, depth + 1), (command.background, depth + 1)))
    return plan
