"""Immutable behavior recipes: compose definitions, then start them with actor.act."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine, Iterable
from dataclasses import KW_ONLY, dataclass
from typing import Generic, TypeVar, cast, overload

from ._bubbles import _validate_text
from ._operations import (
    _context,
    _CostumeRun,
    _During,
    _Join,
    _PoseRun,
    _SoundWait,
    _speak,
    _suspend,
)
from ._scripts import _conflicts, _Fiber
from .audio import Sound, _volume
from .conditions import Condition
from .errors import StageError
from .geometry import Bounds, Point, _integer, _number, _point, _positive
from .imaging import Costume, CostumeSource, _costume
from .messages import Message, Signal
from .motion import Ease
from .puppets import Puppet
from .rigging import Pose
from .sprites import Sprite

type Actor = Sprite | Puppet
"""The two supported behavior targets; not a runtime base class."""
Target_contra = TypeVar("Target_contra", bound=Actor, contravariant=True)
Payload = TypeVar("Payload")


class Block(ABC, Generic[Target_contra]):  # noqa: UP046 -- explicit contravariance is contractual
    """Reusable behavior without target or progress state. Beginners use concrete blocks."""

    __slots__ = ()

    @abstractmethod
    async def run(self, actor: Target_contra) -> None:
        """Advanced execution hook; call actor.act to schedule a root behavior."""


@dataclass(frozen=True, slots=True, init=False)
class Sequence(Block[Target_contra]):
    """Run one or more blocks in order; timed children preserve fractional timing."""

    blocks: tuple[Block[Target_contra], ...]

    def __init__(self, first: Block[Target_contra], *rest: Block[Target_contra]) -> None:
        object.__setattr__(self, "blocks", (first, *rest))

    async def run(self, actor: Target_contra) -> None:
        """Run each child in this invocation."""
        for block in self.blocks:
            await block.run(actor)


@dataclass(frozen=True, slots=True)
class Repeat(Block[Target_contra]):
    """Repeat a block a nonnegative integer number of times; zero does nothing."""

    times: int
    block: Block[Target_contra]

    def __post_init__(self) -> None:
        _integer(self.times, "times", minimum=0)

    async def run(self, actor: Target_contra) -> None:
        """Execute finite repetitions, respecting the shared fairness budget."""
        for _ in range(self.times):
            await _context()
            await self.block.run(actor)


@dataclass(frozen=True, slots=True)
class Loop(Block[Target_contra]):
    """Repeat until canceled; immediate-only iterations yield one simulation tick."""

    block: Block[Target_contra]

    async def run(self, actor: Target_contra) -> None:
        """Repeat without blocking input, drawing, or other actors."""
        while True:
            stage, _, _, before = await _context()
            await self.block.run(actor)
            _, _, _, after = await _context()
            if after <= before:
                await stage.wait(0)


@dataclass(frozen=True, slots=True)
class If(Block[Target_contra]):
    """Evaluate a condition once, then run the selected branch."""

    condition: Condition[Target_contra]
    _: KW_ONLY
    then: Block[Target_contra]
    otherwise: Block[Target_contra] | None = None

    async def run(self, actor: Target_contra) -> None:
        """Test current state, without monitoring in the background."""
        await _context()
        selected = self.then if self.condition.test(actor) else self.otherwise
        if selected is not None:
            await selected.run(actor)


@dataclass(frozen=True, slots=True)
class During(Block[Target_contra]):
    """Run meanwhile alongside foreground; foreground completion closes the background."""

    foreground: Block[Target_contra]
    _: KW_ONLY
    meanwhile: Block[Target_contra]

    async def run(self, actor: Target_contra) -> None:
        """Create two owned branches; neither can outlive this invocation."""
        await _context()
        await _suspend(
            _During(_Fiber(self.foreground.run(actor)), _Fiber(self.meanwhile.run(actor)))
        )


@dataclass(frozen=True, slots=True)
class Script(Block[Target_contra]):
    """Advanced: adapt an async actor function that awaits Plocks operations."""

    function: Callable[[Target_contra], Coroutine[object, object, None]]

    async def run(self, actor: Target_contra) -> None:
        """Run this function within the current cooperative execution."""
        await _context()
        await self.function(actor)


@dataclass(frozen=True, slots=True)
class Say(Block[Actor]):
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
        """Advanced: execute inside Plocks; actor must belong to this stage."""
        await _speak(actor, self)


@dataclass(frozen=True, slots=True)
class Think(Block[Actor]):
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
        """Advanced: execute thought inside the attached actor's Plocks stage."""
        await _speak(actor, self)


@dataclass(frozen=True, slots=True)
class ClearBubble(Block[Actor]):
    """Clear this actor's speech or thought immediately when the block is reached.

    Cancels a timed bubble's whole root, including movement in that root. No timer
    is created. For synchronous use, including while paused, call clear_bubble().
    """

    async def run(self, actor: Actor) -> None:
        """Advanced: clear inside the actor's executing stage."""
        stage, _, _, _ = await _context()
        if actor._stage is not stage:
            raise StageError("Bubble blocks require membership in the executing stage")
        actor.clear_bubble()


@dataclass(frozen=True, slots=True)
class Wait(Block[Actor]):
    """Wait simulated seconds; pause stops the wait and zero yields one tick."""

    seconds: float

    def __post_init__(self) -> None:
        _number(self.seconds, "seconds", minimum=0)

    async def run(self, actor: Actor) -> None:
        """Suspend without blocking the game."""
        stage, _, _, _ = await _context()
        await stage.wait(self.seconds)


@dataclass(frozen=True, slots=True)
class Move(Block[Actor]):
    """Move immediately along direction; one step is one world pixel."""

    steps: float

    def __post_init__(self) -> None:
        _number(self.steps, "steps")

    async def run(self, actor: Actor) -> None:
        """Apply an immediate move when this block is reached."""
        await _context()
        actor.move(self.steps)


def _coordinates(x: float | None, y: float | None) -> None:
    if x is None and y is None:
        raise ValueError("Supply x, y, or both")
    for value in (x, y):
        if value is not None:
            _number(value, "coordinate")


@dataclass(frozen=True, slots=True, kw_only=True)
class MoveTo(Block[Actor]):
    """Set supplied world coordinates immediately; omitted coordinates stay unchanged."""

    x: float | None = None
    y: float | None = None

    def __post_init__(self) -> None:
        _coordinates(self.x, self.y)

    async def run(self, actor: Actor) -> None:
        """Place the actor without collision resolution."""
        await _context()
        actor.move_to(x=self.x, y=self.y)


@dataclass(frozen=True, slots=True, kw_only=True)
class GlideTo(Block[Actor]):
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
        await actor.glide_to(x=self.x, y=self.y, seconds=self.seconds, easing=self.easing)


@dataclass(frozen=True, slots=True, kw_only=True)
class GlideBy(Block[Actor]):
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
        await actor.glide_by(x=self.x, y=self.y, seconds=self.seconds, easing=self.easing)


@dataclass(frozen=True, slots=True)
class TurnLeft(Block[Actor]):
    """Turn immediately counterclockwise, in degrees."""

    degrees: float

    def __post_init__(self) -> None:
        _number(self.degrees, "degrees")

    async def run(self, actor: Actor) -> None:
        """Change direction when reached."""
        await _context()
        actor.turn_left(self.degrees)


@dataclass(frozen=True, slots=True)
class TurnRight(Block[Actor]):
    """Turn immediately clockwise, in degrees."""

    degrees: float

    def __post_init__(self) -> None:
        _number(self.degrees, "degrees")

    async def run(self, actor: Actor) -> None:
        """Change direction when reached."""
        await _context()
        actor.turn_right(self.degrees)


@dataclass(frozen=True, slots=True)
class PointTowards(Block[Actor]):
    """Face a world point or an actor's position sampled when reached."""

    target: Point | Actor

    def __post_init__(self) -> None:
        if isinstance(self.target, tuple):
            _point(self.target)

    async def run(self, actor: Actor) -> None:
        """Point immediately; coincident positions leave direction unchanged."""
        await _context()
        actor.point_towards(self.target)


@dataclass(frozen=True, slots=True)
class GoToRandom(Block[Actor]):
    """Place the anchor randomly in bounds, defaulting to the visible world."""

    bounds: Bounds | None = None

    async def run(self, actor: Actor) -> None:
        """Sample a new position when reached; does not guarantee the whole image fits."""
        await _context()
        actor.go_to_random(self.bounds)


@dataclass(frozen=True, slots=True)
class BounceOnEdge(Block[Actor]):
    """Reflect outward movement and fit inside bounds; this is an immediate operation."""

    bounds: Bounds | None = None

    async def run(self, actor: Actor) -> None:
        """Bounce against supplied bounds or the visible world."""
        await _context()
        actor.bounce_on_edge(self.bounds)


@dataclass(frozen=True, slots=True, init=False)
class SetCostume(Block[Sprite]):
    """Set a sprite image, canceling any current timed costume writer."""

    costume: Costume

    def __init__(self, costume: CostumeSource) -> None:
        object.__setattr__(self, "costume", _costume(costume))

    async def run(self, actor: Sprite) -> None:
        """Assign the immutable costume when reached."""
        await _context()
        actor.costume = self.costume


@dataclass(frozen=True, slots=True, init=False)
class Costumes(Block[Sprite]):
    """One timed frame pass, including the final frame interval; use Loop to repeat."""

    frames: tuple[Costume, ...]
    fps: float

    def __init__(self, frames: Iterable[CostumeSource], *, fps: float) -> None:
        copied = tuple(_costume(frame) for frame in frames)
        if not copied:
            raise ValueError("Costumes needs at least one frame")
        object.__setattr__(self, "frames", copied)
        object.__setattr__(self, "fps", _positive(fps, "fps"))
        _number(len(copied) / self.fps, "costume duration")

    async def run(self, actor: Sprite) -> None:
        """Display first frame immediately, then sample using simulation time."""
        stage, root, _, at = await _context()
        if actor._stage is not stage:
            raise StageError("Costumes requires membership in the executing stage")
        _number(at + len(self.frames) / self.fps, "costume deadline")
        _conflicts(actor, False, False, root, visual=True)
        operation = _CostumeRun(actor, self, at)
        actor._visual = operation
        await _suspend(operation)


@dataclass(frozen=True, slots=True)
class SetPose(Block[Puppet]):
    """Set a complete Puppet pose; its skeleton must match the target instance."""

    pose: Pose

    async def run(self, actor: Puppet) -> None:
        """Assign the pose and cancel any timed pose writer."""
        await _context()
        actor.pose = self.pose


@dataclass(frozen=True, slots=True, init=False)
class Poses(Block[Puppet]):
    """Interpolate first to last pose, one interval per 1/fps seconds; explicitly close loops."""

    poses: tuple[Pose, ...]
    fps: float

    def __init__(self, poses: Iterable[Pose], *, fps: float) -> None:
        copied = tuple(poses)
        if not copied or any(p.skeleton is not copied[0].skeleton for p in copied):
            raise ValueError("Poses needs poses sharing one exact skeleton")
        object.__setattr__(self, "poses", copied)
        object.__setattr__(self, "fps", _positive(fps, "fps"))
        _number((len(copied) - 1) / self.fps, "pose duration")

    async def run(self, actor: Puppet) -> None:
        """Sample shortest angles; exact 180-degree ties turn clockwise."""
        stage, root, _, at = await _context()
        if actor._stage is not stage:
            raise StageError("Poses requires membership in the executing stage")
        if actor.skeleton is not self.poses[0].skeleton:
            raise ValueError("Poses belongs to another skeleton")
        _number(at + (len(self.poses) - 1) / self.fps, "pose deadline")
        _conflicts(actor, False, False, root, visual=True)
        if len(self.poses) == 1:
            actor._pose = self.poses[0]
        else:
            operation = _PoseRun(actor, self, at)
            actor._pose = operation
            await _suspend(operation)


@dataclass(frozen=True, slots=True, init=False)
class SetPartCostume(Block[Puppet]):
    """Replace an existing Puppet attachment; its pose motion continues."""

    joint: str
    costume: Costume

    def __init__(self, joint: str, costume: CostumeSource) -> None:
        object.__setattr__(self, "joint", joint)
        object.__setattr__(self, "costume", _costume(costume))

    async def run(self, actor: Puppet) -> None:
        """Replace an attachment; unknown attachment keys raise KeyError."""
        await _context()
        actor.set_part_costume(self.joint, self.costume)


@dataclass(frozen=True, slots=True)
class PlaySound(Block[Actor]):
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


@dataclass(frozen=True, slots=True, init=False)
class Broadcast(Block[Actor]):
    """Queue a signal or matching typed payload; receivers run in a later delivery cycle."""

    message: Signal | Message[object]
    data: object

    @overload
    def __init__(self, message: Signal) -> None: ...
    @overload
    def __init__(self, message: Message[Payload], data: Payload) -> None: ...
    def __init__(self, message: Signal | Message[Payload], data: Payload | None = None) -> None:
        object.__setattr__(self, "message", cast("Signal | Message[object]", message))
        object.__setattr__(self, "data", data)

    async def run(self, actor: Actor) -> None:
        """Emit without waiting for receiver completion."""
        stage, _, _, _ = await _context()
        stage._enqueue(self.message, self.data)


@dataclass(frozen=True, slots=True, init=False)
class BroadcastAndWait(Block[Actor]):
    """Deliver a message and join only the receiver invocations accepted for it."""

    message: Signal | Message[object]
    data: object

    @overload
    def __init__(self, message: Signal) -> None: ...
    @overload
    def __init__(self, message: Message[Payload], data: Payload) -> None: ...
    def __init__(self, message: Signal | Message[Payload], data: Payload | None = None) -> None:
        object.__setattr__(self, "message", cast("Signal | Message[object]", message))
        object.__setattr__(self, "data", data)

    async def run(self, actor: Actor) -> None:
        """Wait for accepted roots; cancellation does not retract the delivery."""
        stage, _, _, _ = await _context()
        await _suspend(_Join(stage._enqueue(self.message, self.data)))
