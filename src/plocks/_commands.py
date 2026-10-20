"""Immutable internal command definitions; public authoring uses actor methods and Scripts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import KW_ONLY, dataclass
from typing import TYPE_CHECKING, Generic, TypeVar, cast

from ._bubbles import _validate_text
from ._operations import (
    _context,
    _During,
    _ImageRun,
    _PoseRun,
    _SoundWait,
    _speak,
    _suspend,
)
from ._scripts import _conflicts, _Fiber
from .actions import Action
from .audio import Sound, _volume
from .conditions import Condition, _test
from .errors import StageError
from .geometry import Bounds, Point, _number, _point, _positive
from .imaging import Image, ImageSource, _image
from .messages import Message
from .motion import Ease
from .physics import Body
from .puppets import Puppet
from .rigging import Pose
from .sprites import Sprite

if TYPE_CHECKING:
    from .stage import Stage

type Actor = Sprite | Puppet
"""The two supported behavior targets; not a runtime base class."""
Target_contra = TypeVar("Target_contra", bound=Actor, contravariant=True)
Payload = TypeVar("Payload")


class _Command(ABC, Generic[Target_contra]):  # noqa: UP046 -- explicit contravariance is contractual
    """Immutable command script without progress state; Scripts compose these internally."""

    __slots__ = ()

    @abstractmethod
    async def run(self, actor: Target_contra) -> None:
        """Private execution hook; actor.act admits a root Script."""


@dataclass(frozen=True, slots=True)
class _Plan(_Command[Target_contra]):
    target_type: type[Sprite | Puppet] | None
    commands: tuple[_Command[Target_contra], ...]
    times: int | None

    async def run(self, actor: Target_contra) -> None:
        remaining = self.times
        while remaining is None or remaining > 0:
            stage, _, _, before = await _context()
            for command in self.commands:
                await _context()
                await command.run(actor)
            _, _, _, after = await _context()
            if remaining is not None:
                remaining -= 1
            if after <= before and (remaining is None or remaining > 0):
                from ._operations import _wait

                await _wait(stage, 0)


@dataclass(frozen=True, slots=True)
class _When(_Command[Target_contra]):
    condition: Condition
    then: _Command[Target_contra]
    either: _Command[Target_contra] | None

    async def run(self, actor: Target_contra) -> None:
        await _context()
        selected = self.then if _test(self.condition, actor) else self.either
        if selected is not None:
            await selected.run(actor)


@dataclass(frozen=True, slots=True)
class _DuringPlan(_Command[Target_contra]):
    """Run meanwhile alongside foreground; foreground completion closes the background."""

    foreground: _Command[Target_contra]
    _: KW_ONLY
    background: _Command[Target_contra]

    async def run(self, actor: Target_contra) -> None:
        """Create two owned branches; neither can outlive this invocation."""
        await _context()
        await _suspend(
            _During(_Fiber(self.foreground.run(actor)), _Fiber(self.background.run(actor)))
        )


@dataclass(frozen=True, slots=True)
class _Say(_Command[Actor]):
    """Show speech; omit seconds to persist, or wait simulated seconds then clear.

    Text is captured at construction (including f-strings). A timed bubble claims
    this actor's bubble: replacement cancels its entire root behavior. Pause stops
    its clock; zero yields one tick without guaranteeing a displayed frame.
    """

    text: str
    _: KW_ONLY
    seconds: float | None = None

    def __post_init__(self) -> None:
        _validate_text(self.text)
        if self.seconds is not None:
            _number(self.seconds, "seconds", minimum=0)

    async def run(self, actor: Actor) -> None:
        """Internal: execute inside Plocks; actor must belong to this stage."""
        await _speak(actor, self)


@dataclass(frozen=True, slots=True)
class _Think(_Command[Actor]):
    """Show thought; omit seconds to persist, or wait simulated seconds then clear.

    Shares one bubble with speech. Text is captured at construction; replacement
    cancels an active timed bubble's entire root. Zero yields one simulation tick.
    """

    text: str
    _: KW_ONLY
    seconds: float | None = None

    def __post_init__(self) -> None:
        _validate_text(self.text)
        if self.seconds is not None:
            _number(self.seconds, "seconds", minimum=0)

    async def run(self, actor: Actor) -> None:
        """Internal: execute thought inside the attached actor's Plocks stage."""
        await _speak(actor, self)


@dataclass(frozen=True, slots=True)
class _ClearBubble(_Command[Actor]):
    """Clear this actor's speech or thought immediately when the block is reached.

    Cancels a timed bubble's whole root, including movement in that root. No timer
    is created. For synchronous use, including while paused, call clear_bubble().
    """

    async def run(self, actor: Actor) -> None:
        """Internal: clear inside the actor's executing stage."""
        stage, _, _, _ = await _context()
        if actor._stage is not stage:
            raise StageError("Bubble blocks require membership in the executing stage")
        _conflicts(actor, False, False, bubble=True)
        actor._bubble = None


@dataclass(frozen=True, slots=True)
class _Wait(_Command[Actor]):
    """_Wait simulated seconds; pause stops the wait and zero yields one tick."""

    seconds: float

    def __post_init__(self) -> None:
        _number(self.seconds, "seconds", minimum=0)

    async def run(self, actor: Actor) -> None:
        """Suspend without blocking the game."""
        stage, _, _, _ = await _context()
        from ._operations import _wait

        await _wait(stage, self.seconds)


@dataclass(frozen=True, slots=True)
class _Move(_Command[Actor]):
    """_Move immediately along direction; one step is one world pixel."""

    steps: float

    def __post_init__(self) -> None:
        _number(self.steps, "steps")

    async def run(self, actor: Actor) -> None:
        """Apply an immediate move when this block is reached."""
        await _context()
        from .motion import _move

        _move(actor, self.steps)


def _coordinates(x: float | None, y: float | None) -> None:
    if x is None and y is None:
        raise ValueError("Supply x, y, or both")
    for value in (x, y):
        if value is not None:
            _number(value, "coordinate")


@dataclass(frozen=True, slots=True, kw_only=True)
class _MoveTo(_Command[Actor]):
    """Set supplied world coordinates immediately; omitted coordinates stay unchanged."""

    x: float | None = None
    y: float | None = None

    def __post_init__(self) -> None:
        _coordinates(self.x, self.y)

    async def run(self, actor: Actor) -> None:
        """Place the actor without collision resolution."""
        await _context()
        from .motion import _move_to

        _move_to(actor, self.x, self.y)


@dataclass(frozen=True, slots=True, kw_only=True)
class _GlideTo(_Command[Actor]):
    """Glide to world coordinates in simulated seconds; only supplied axes are controlled."""

    seconds: float
    x: float | None = None
    y: float | None = None
    easing: Ease = Ease.LINEAR

    def __post_init__(self) -> None:
        _coordinates(self.x, self.y)
        _number(self.seconds, "seconds", minimum=0)
        if not isinstance(self.easing, Ease):
            raise TypeError("Use an Ease value")

    async def run(self, actor: Actor) -> None:
        """Await absolute motion; competing writers cancel their previous root."""
        from ._operations import _glide

        await _glide(actor, self.x, self.y, self.seconds, self.easing, relative=False)


@dataclass(frozen=True, slots=True, init=False)
class _FollowPath(_Command[Actor]):
    """Snapshot waypoints; existing glide requests own each segment's progress."""

    points: tuple[Point, ...]
    speed: float

    def __init__(self, points: Iterable[Point], *, speed: float = 100) -> None:
        values = tuple(_point(point, "waypoint") for point in points)
        if not values:
            raise ValueError("A path requires at least one waypoint")
        object.__setattr__(self, "points", values)
        object.__setattr__(self, "speed", _positive(speed, "speed"))

    async def run(self, actor: Actor) -> None:
        from math import hypot

        from ._operations import _glide

        await _context()
        for x, y in self.points:
            distance = _number(hypot(x - actor.x, y - actor.y), "segment distance")
            if distance:
                await _glide(actor, x, y, distance / self.speed, Ease.LINEAR, relative=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class _GlideBy(_Command[Actor]):
    """Glide by world pixels in simulated seconds, capturing position when reached."""

    seconds: float
    x: float | None = None
    y: float | None = None
    easing: Ease = Ease.LINEAR

    def __post_init__(self) -> None:
        _coordinates(self.x, self.y)
        _number(self.seconds, "seconds", minimum=0)
        if not isinstance(self.easing, Ease):
            raise TypeError("Use an Ease value")

    async def run(self, actor: Actor) -> None:
        """Await relative motion; omitted axes remain available to other behaviors."""
        from ._operations import _glide

        await _glide(actor, self.x, self.y, self.seconds, self.easing, relative=True)


@dataclass(frozen=True, slots=True)
class _TurnLeft(_Command[Actor]):
    """Turn immediately counterclockwise, in degrees."""

    degrees: float

    def __post_init__(self) -> None:
        _number(self.degrees, "degrees")

    async def run(self, actor: Actor) -> None:
        """Change direction when reached."""
        await _context()
        actor.direction -= self.degrees


@dataclass(frozen=True, slots=True)
class _TurnRight(_Command[Actor]):
    """Turn immediately clockwise, in degrees."""

    degrees: float

    def __post_init__(self) -> None:
        _number(self.degrees, "degrees")

    async def run(self, actor: Actor) -> None:
        """Change direction when reached."""
        await _context()
        actor.direction += self.degrees


@dataclass(frozen=True, slots=True)
class _PointTowards(_Command[Actor]):
    """Face a world point or an actor's position sampled when reached."""

    target: Point | Actor

    def __post_init__(self) -> None:
        if isinstance(self.target, tuple):
            _point(self.target)

    async def run(self, actor: Actor) -> None:
        """Point immediately; coincident positions leave direction unchanged."""
        await _context()
        from .motion import _point_towards

        if isinstance(self.target, (Sprite, Puppet)) and self.target._stage is not actor._stage:
            raise StageError("Point target must belong to the executing stage")
        _point_towards(actor, self.target)


@dataclass(frozen=True, slots=True)
class _GoToRandom(_Command[Actor]):
    """Place the anchor randomly in bounds, defaulting to the visible world."""

    bounds: Bounds | None = None

    async def run(self, actor: Actor) -> None:
        """Sample a new position when reached; does not guarantee the whole image fits."""
        await _context()
        from .motion import _random

        _random(actor, self.bounds)


@dataclass(frozen=True, slots=True)
class _BounceOnEdge(_Command[Actor]):
    """Reflect outward movement and fit inside bounds; this is an immediate operation."""

    bounds: Bounds | None = None

    async def run(self, actor: Actor) -> None:
        """Bounce against supplied bounds or the visible world."""
        await _context()
        from .motion import _bounce

        _bounce(actor, self.bounds)


@dataclass(frozen=True, slots=True, init=False)
class _SetImage(_Command[Sprite]):
    """Set a sprite image, canceling any current timed image writer."""

    image: Image

    def __init__(self, image: ImageSource) -> None:
        object.__setattr__(self, "image", _image(image))

    async def run(self, actor: Sprite) -> None:
        """Assign the immutable image when reached."""
        await _context()
        actor.image = self.image


@dataclass(frozen=True, slots=True, init=False)
class _Images(_Command[Sprite]):
    """One timed frame pass, including the final frame interval; use Script.repeat to repeat."""

    frames: tuple[Image, ...]
    durations: tuple[float, ...]

    def __init__(
        self,
        frames: Iterable[ImageSource],
        *,
        fps: float | None = None,
        durations: Iterable[float] | None = None,
    ) -> None:
        if (fps is None) == (durations is None):
            raise ValueError("Supply exactly one of fps or durations")
        copied = tuple(_image(frame) for frame in frames)
        if not copied:
            raise ValueError("Images needs at least one frame")
        holds = (
            tuple(_positive(value, "frame duration") for value in durations)
            if durations is not None
            else (1 / _positive(cast(float, fps), "fps"),) * len(copied)
        )
        if len(holds) != len(copied):
            raise ValueError("durations must have one positive duration per frame")
        _number(sum(holds), "image duration")
        object.__setattr__(self, "frames", copied)
        object.__setattr__(self, "durations", holds)

    async def run(self, actor: Sprite) -> None:
        """Display first frame immediately, then sample using simulation time."""
        stage, root, _, at = await _context()
        if actor._stage is not stage:
            raise StageError("_Images requires membership in the executing stage")
        _number(at + sum(self.durations), "image deadline")
        _conflicts(actor, False, False, root, visual=True)
        operation = _ImageRun(actor, self, at)
        actor._visual = operation
        await _suspend(operation)


@dataclass(frozen=True, slots=True)
class _SetPose(_Command[Puppet]):
    """Set a complete Puppet pose; its skeleton must match the target instance."""

    pose: Pose

    async def run(self, actor: Puppet) -> None:
        """Assign the pose and cancel any timed pose writer."""
        await _context()
        actor.pose = self.pose


@dataclass(frozen=True, slots=True, init=False)
class _Poses(_Command[Puppet]):
    """Interpolate first to last pose, one interval per 1/fps seconds; explicitly close loops."""

    poses: tuple[Pose, ...]
    fps: float

    def __init__(self, poses: Iterable[Pose], *, fps: float) -> None:
        copied = tuple(poses)
        if not copied or any(p.skeleton is not copied[0].skeleton for p in copied):
            raise ValueError("_Poses needs poses sharing one exact skeleton")
        object.__setattr__(self, "poses", copied)
        object.__setattr__(self, "fps", _positive(fps, "fps"))
        _number((len(copied) - 1) / self.fps, "pose duration")

    async def run(self, actor: Puppet) -> None:
        """Sample shortest angles; exact 180-degree ties turn clockwise."""
        stage, root, _, at = await _context()
        if actor._stage is not stage:
            raise StageError("_Poses requires membership in the executing stage")
        if actor.skeleton is not self.poses[0].skeleton:
            raise ValueError("_Poses belongs to another skeleton")
        _number(at + (len(self.poses) - 1) / self.fps, "pose deadline")
        _conflicts(actor, False, False, root, visual=True)
        if len(self.poses) == 1:
            actor._pose = self.poses[0]
        else:
            operation = _PoseRun(actor, self, at)
            actor._pose = operation
            await _suspend(operation)


@dataclass(frozen=True, slots=True, init=False)
class _SetPartImage(_Command[Puppet]):
    """Replace an existing Puppet attachment; its pose motion continues."""

    joint: str
    image: Image

    def __init__(self, joint: str, image: ImageSource) -> None:
        object.__setattr__(self, "joint", joint)
        object.__setattr__(self, "image", _image(image))

    async def run(self, actor: Puppet) -> None:
        """Replace an attachment; unknown attachment keys raise KeyError."""
        await _context()
        if self.joint not in actor._parts:
            raise KeyError(self.joint)
        actor._parts[self.joint] = self.image


@dataclass(frozen=True, slots=True)
class _PlaySound(_Command[Actor]):
    """Play one OGG occurrence; waiting is default and cancellation stops that occurrence."""

    sound: Sound
    _: KW_ONLY
    volume: float = 1.0
    wait: bool = True

    def __post_init__(self) -> None:
        _volume(self.volume)

    async def run(self, actor: Actor) -> None:
        """Optionally await channel completion; nonwaiting voices remain stage-owned."""
        stage, _, _, _ = await _context()
        voice = stage.play(self.sound, volume=self.volume)
        if self.wait:
            await _suspend(_SoundWait(voice))


@dataclass(frozen=True, slots=True)
class _Send(_Command[Actor]):
    message: Message[object]
    data: object
    target: Actor | None
    wait_receivers: bool

    async def run(self, actor: Actor) -> None:
        await _send(self.message, self.data, actor, self.target, self.wait_receivers)


async def _send(
    message: Message[object],
    data: object,
    source: Stage | Actor,
    target: Actor | None,
    wait_receivers: bool,
) -> None:
    from ._operations import _JoinDelivery

    stage, _, _, _ = await _context()
    if isinstance(source, (Sprite, Puppet)) and source._stage is not stage:
        raise StageError("Message source must belong to the executing stage")
    await _suspend(_JoinDelivery(stage._enqueue(message, source, data, target), wait_receivers))


@dataclass(frozen=True, slots=True)
class _JoinActions(_Command[Actor]):
    actions: tuple[Action, ...]

    async def run(self, actor: Actor) -> None:
        await _join(self.actions)


async def _join(actions: tuple[Action, ...]) -> None:
    from ._operations import _AwaitAll
    from .errors import ActionCancelled

    await _suspend(_AwaitAll(actions))
    for action in actions:
        if action.cancelled:
            raise ActionCancelled("A joined action was canceled")
        if action.exception is not None:
            raise action.exception


_Target = TypeVar("_Target", bound=Actor)


def _schedule(actor: _Target, command: _Command[_Target], *, after: Action | None = None) -> Action:  # noqa: UP047 -- shared contravariant binding
    from ._scripts import _admit

    stage = actor._stage
    if stage is None:
        raise StageError("Add the actor to a stage before scheduling commands")
    return _admit(stage, command.run(actor), actor, after=after)


@dataclass(frozen=True, slots=True)
class _Impulse(_Command[Actor]):
    body: Body
    x: float
    y: float
    point: Point | None

    def __post_init__(self) -> None:
        _point((self.x, self.y), "impulse")
        if self.point is not None:
            object.__setattr__(self, "point", _point(self.point, "at"))

    async def run(self, actor: Actor) -> None:
        from .physics import _dynamic

        await _context()
        native = _dynamic(self.body)
        point = (
            native.local_to_world(native.center_of_gravity) if self.point is None else self.point
        )
        native.apply_impulse_at_world_point((self.x, self.y), point)


@dataclass(frozen=True, slots=True)
class _Force(_Command[Actor]):
    body: Body
    x: float
    y: float
    seconds: float | None
    point: Point | None

    def __post_init__(self) -> None:
        _point((self.x, self.y), "force")
        if self.point is not None:
            object.__setattr__(self, "point", _point(self.point, "at"))
        if self.seconds is not None:
            _number(self.seconds, "seconds", minimum=0)

    async def run(self, actor: Actor) -> None:
        from ._operations import _Delay, _ForceRun
        from .physics import _dynamic

        stage, _, _, at = await _context()
        _dynamic(self.body)
        seconds = 1 / stage.tick_rate if self.seconds is None else self.seconds
        _number(at + seconds, "force deadline")
        if seconds:
            await _suspend(_ForceRun(self.body, (self.x, self.y), self.point, at, seconds))
        else:
            await _suspend(_Delay(stage.time + 1 / stage.tick_rate))


@dataclass(frozen=True, slots=True)
class _Torque(_Command[Actor]):
    body: Body
    amount: float
    seconds: float | None

    def __post_init__(self) -> None:
        _number(self.amount, "torque")
        if self.seconds is not None:
            _number(self.seconds, "seconds", minimum=0)

    async def run(self, actor: Actor) -> None:
        from ._operations import _Delay, _TorqueRun
        from .physics import _dynamic

        stage, _, _, at = await _context()
        _dynamic(self.body)
        seconds = 1 / stage.tick_rate if self.seconds is None else self.seconds
        _number(at + seconds, "torque deadline")
        if seconds:
            await _suspend(_TorqueRun(self.body, self.amount, at, seconds))
        else:
            await _suspend(_Delay(stage.time + 1 / stage.tick_rate))
