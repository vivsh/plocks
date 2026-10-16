"""Articulated image actors with immutable skeletons and one current pose."""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Iterable, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, TypeVar, cast, overload

from ._operations import _PoseRun, _sample_pose
from ._scripts import WhenBusy, _conflicts
from .actions import Action
from .audio import Sound
from .geometry import (
    Bounds,
    Color,
    Point,
    _integer,
    _number,
    _Placement,
    _point,
    _positive,
    _rotate,
)
from .imaging import Costume, CostumeSource, _costume
from .input import Key, MouseButton
from .messages import Message, Signal
from .motion import (
    Ease,
    RotationStyle,
    _body_direction,
    _body_position,
    _mirrored,
    _visual_direction,
)
from .physics import Body, BodyType
from .rigging import HumanJoint, Pose, Skeleton, _pivots

if TYPE_CHECKING:
    from ._commands import Actor, _Say, _Think
    from ._operations import _BubbleRun
    from .groups import PuppetGroup
    from .sprites import Sprite
    from .stage import Stage
    from .tiling import TileMap


_D = TypeVar("_D")
_R = TypeVar("_R", bound=None | Action | Coroutine[object, object, None])
type _Press = Callable[[], None | Action | Coroutine[object, object, None]]
_P = TypeVar("_P", bound=_Press)
_U = TypeVar("_U", bound=Callable[[float], None])
_C = TypeVar(
    "_C", bound=Callable[[Point, MouseButton], None | Action | Coroutine[object, object, None]]
)


class Puppet:
    """An articulated image actor. Construct it, then add it with stage.add(puppet).

    Positions use logical pixels and the costume anchor. Commands schedule Actions;
    property assignments apply immediately. Direction 90 faces right.
    """

    __slots__ = (
        "_bubble",
        "_layer",
        "_parts",
        "_pose",
        "_rotation_style",
        "_scale",
        "_skeleton",
        "_stage",
        "_transform",
        "_visible",
    )

    def __init__(
        self,
        skeleton: Skeleton,
        *,
        parts: Mapping[str, CostumeSource],
        pose: Pose | None = None,
        body_type: BodyType = BodyType.DYNAMIC,
    ) -> None:
        if not parts or any(name not in skeleton.joints for name in parts):
            raise ValueError("Supply at least one image part on existing joints")
        self._skeleton = skeleton
        self._parts = {name: _costume(source) for name, source in parts.items()}
        initial = skeleton.rest_pose() if pose is None else pose
        if initial.skeleton is not skeleton:
            raise ValueError("Pose belongs to another skeleton")
        self._pose: Pose | _PoseRun = initial
        self._transform: _Placement | Body = _Placement((0, 0), 90, body_type)
        self._scale = 1.0
        self._visible = True
        self._layer = 0
        if not isinstance(body_type, BodyType):
            raise TypeError("Use a BodyType value")
        self._stage: Stage | None = None
        self._rotation_style = RotationStyle.ALL_AROUND
        self._bubble: _Say | _Think | _BubbleRun | None = None

    @property
    def skeleton(self) -> Skeleton:
        """Immutable topology; poses must reference this exact instance."""
        return self._skeleton

    @property
    def parts(self) -> Mapping[str, Costume]:
        """Read-only image attachments in painting order; keys remain fixed."""
        return MappingProxyType(self._parts)

    @staticmethod
    def stick_figure(*, color: Color = "white", stroke_width: float = 4.0) -> Puppet:
        """Create a human Puppet using generated capsule/disc costumes; no files needed."""
        return _stick_figure(color, stroke_width)

    @property
    def body(self) -> Body:
        """Current physical attachment; raises PhysicsError when detached or physics is off."""
        from .errors import PhysicsError

        if not isinstance(self._transform, Body):
            raise PhysicsError("Add this actor to Stage(physics=True) with a physical body_type")
        return self._transform

    @property
    def body_type(self) -> BodyType:
        """Configured role, always readable; change only while detached."""
        return self._transform.body_type

    @body_type.setter
    def body_type(self, value: BodyType) -> None:
        from .errors import PhysicsError

        if not isinstance(value, BodyType):
            raise TypeError("Use a BodyType value")
        if self._stage is not None:
            raise PhysicsError("Change body_type only while detached")
        self._transform = _Placement(self.position, self.direction, value)

    @property
    def x(self) -> float:
        """Anchor x in world pixels; increasing x moves right."""
        return self.position[0]

    @x.setter
    def x(self, value: float) -> None:
        value = _number(value, "x")
        _conflicts(self, True, False)
        from .motion import _set_position

        _set_position(self, (value, self.y))

    @property
    def y(self) -> float:
        """Anchor y in world pixels; increasing y moves upward."""
        return self.position[1]

    @y.setter
    def y(self, value: float) -> None:
        value = _number(value, "y")
        _conflicts(self, False, True)
        from .motion import _set_position

        _set_position(self, (self.x, value))

    @property
    def position(self) -> Point:
        """The same coordinates as (x, y), measured at the costume anchor."""
        return (
            self._transform.position
            if isinstance(self._transform, _Placement)
            else _body_position(self._transform)
        )

    @position.setter
    def position(self, value: Point) -> None:
        point = _point(value)
        _conflicts(self, True, True)
        from .motion import _set_position

        _set_position(self, point)

    @property
    def direction(self) -> float:
        """Clockwise degrees from up: 0 up, 90 right, 180 down, 270 left."""
        return (
            self._transform.direction
            if isinstance(self._transform, _Placement)
            else _body_direction(self._transform)
        )

    @direction.setter
    def direction(self, value: float) -> None:
        from .motion import _set_direction

        _set_direction(self, _number(value, "direction") % 360)

    @property
    def scale(self) -> float:
        """Positive uniform size multiplier; 1.0 is the source size."""
        return self._scale

    @scale.setter
    def scale(self, value: float) -> None:
        value = _positive(value, "scale")
        if isinstance(self._transform, Body):
            from ._physics import _replace_shape

            _replace_shape(self._transform, self._transform.shape, value)
        self._scale = value

    @property
    def visible(self) -> bool:
        """Whether the sprite is drawn; collision queries still include it."""
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self._visible = value

    @property
    def layer(self) -> int:
        """Drawing layer; higher numbers appear above lower numbers."""
        return self._layer

    @layer.setter
    def layer(self, value: int) -> None:
        self._layer = _integer(value, "layer")

    @property
    def pose(self) -> Pose:
        """Current complete pose; assigning a pose cancels its active pose writer."""
        if isinstance(self._pose, _PoseRun):
            assert self._stage is not None
            return _sample_pose(self._pose, self._stage.time)
        return self._pose

    @pose.setter
    def pose(self, value: Pose) -> None:
        if value.skeleton is not self.skeleton:
            raise ValueError("Pose belongs to another skeleton")
        _conflicts(self, False, False, visual=True)
        self._pose = value

    @property
    def bounds(self) -> Bounds:
        """World AABB of all image corners, including transparent padding."""
        return _bounds(self, self.direction)

    def touching(self, other: Sprite | Puppet | TileMap) -> bool:
        """Test AABB overlap, or solid tile overlap. Visibility does not affect it."""
        from .tiling import TileMap

        if isinstance(other, TileMap):
            return bool(other.tiles_touching(self.bounds, solid_only=True))
        return self.bounds.intersects(other.bounds)

    def on_update(self, callback: _U) -> _U:
        """Decorate a synchronous callback(dt: float) -> None; attach this actor first.

        Runs each fixed simulation tick in registration order, including while
        hidden. Pausing stops updates. The stage skips this callback while the
        actor is detached and clears it on closure. Detached registration raises
        StageError. Use groups for reusable behaviors; async updates are rejected.
        """
        from .errors import StageError

        if self._stage is None:
            raise StageError("Add the actor to a stage before registering events")
        return self._stage._on_actor_update(self, callback)

    @overload
    def on_click(self, work: _C, *, when_busy: WhenBusy = WhenBusy.IGNORE) -> _C: ...
    @overload
    def on_click(self, work: PuppetGroup, *, when_busy: WhenBusy = WhenBusy.IGNORE) -> None: ...
    def on_click(self, work: object, *, when_busy: WhenBusy = WhenBusy.IGNORE) -> object:
        """Bind a recipe or decorate a click callback for this topmost visible actor."""
        from .stage import _attached

        return _attached(self)._on_actor_click(self, work, when_busy)

    @overload
    def on_start(self, work: _P) -> _P: ...
    @overload
    def on_start(self, work: PuppetGroup) -> None: ...
    def on_start(self, work: object) -> object:
        """Run a recipe or callback at game startup; attach first and register before run."""
        from .stage import _attached

        return _attached(self)._on_actor_start(self, work)

    @overload
    def on_key_down(
        self, key: Key, *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> Callable[[_P], _P]: ...
    @overload
    def on_key_down(
        self, key: Key, group: PuppetGroup, *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> None: ...
    def on_key_down(
        self, key: Key, group: PuppetGroup | None = None, *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> object:
        """Handle a fresh key press; return Action to stay busy until it completes."""
        from .stage import _attached

        stage = _attached(self)
        if group is not None:
            return stage.on_key_down(key, self, group, when_busy=when_busy)
        return stage._key_decorator(key, self, when_busy)

    @overload
    def on_message(
        self, message: Signal, *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> Callable[[_P], _P]: ...
    @overload
    def on_message(
        self, message: Message[_D], *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> Callable[[Callable[[_D], _R]], Callable[[_D], _R]]: ...
    @overload
    def on_message(
        self,
        message: Signal | Message[_D],
        group: PuppetGroup,
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None: ...
    def on_message(
        self,
        message: Signal | Message[_D],
        group: PuppetGroup | None = None,
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> object:
        """Receive typed messages; return an Action for structured lifetime and busy protection."""
        from .stage import _attached

        stage = _attached(self)
        if group is not None:
            return stage.on_message(message, self, group, when_busy=when_busy)
        return stage._message_decorator(cast("Signal | Message[object]", message), self, when_busy)

    def move(self, steps: float, *, after: Action | None = None) -> Action:
        """Move along direction in logical pixels when reached.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _Move, _schedule

        return _schedule(self, _Move(steps), after=after)

    def move_to(
        self, *, x: float | None = None, y: float | None = None, after: Action | None = None
    ) -> Action:
        """Set supplied world coordinates when reached; omitted axes stay unchanged.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _MoveTo, _schedule

        return _schedule(self, _MoveTo(x=x, y=y), after=after)

    def glide_to(
        self,
        *,
        x: float | None = None,
        y: float | None = None,
        seconds: float,
        easing: Ease = Ease.LINEAR,
        after: Action | None = None,
    ) -> Action:
        """Glide to world coordinates over simulated seconds; omitted axes stay free.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _GlideTo, _schedule

        return _schedule(self, _GlideTo(x=x, y=y, seconds=seconds, easing=easing), after=after)

    def glide_by(
        self,
        *,
        x: float | None = None,
        y: float | None = None,
        seconds: float,
        easing: Ease = Ease.LINEAR,
        after: Action | None = None,
    ) -> Action:
        """Glide by logical pixels, capturing the starting position when execution begins.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _GlideBy, _schedule

        return _schedule(self, _GlideBy(x=x, y=y, seconds=seconds, easing=easing), after=after)

    def wait(self, seconds: float, *, after: Action | None = None) -> Action:
        """Wait simulated seconds; pause freezes progress and zero yields one tick.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _schedule, _Wait

        return _schedule(self, _Wait(seconds), after=after)

    def turn_left(self, degrees: float, *, after: Action | None = None) -> Action:
        """Turn counterclockwise by degrees when reached.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _schedule, _TurnLeft

        return _schedule(self, _TurnLeft(degrees), after=after)

    def turn_right(self, degrees: float, *, after: Action | None = None) -> Action:
        """Turn clockwise by degrees when reached.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _schedule, _TurnRight

        return _schedule(self, _TurnRight(degrees), after=after)

    def point_towards(self, target: Point | Actor, *, after: Action | None = None) -> Action:
        """Face a world point or the target actor position sampled when reached.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _PointTowards, _schedule

        return _schedule(self, _PointTowards(target), after=after)

    def go_to_random(self, bounds: Bounds | None = None, *, after: Action | None = None) -> Action:
        """Choose an anchor position uniformly in bounds, or the visible world.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _GoToRandom, _schedule

        return _schedule(self, _GoToRandom(bounds), after=after)

    def bounce_on_edge(
        self, bounds: Bounds | None = None, *, after: Action | None = None
    ) -> Action:
        """Fit within bounds and reflect outward motion; oversized actors raise ValueError.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _BounceOnEdge, _schedule

        return _schedule(self, _BounceOnEdge(bounds), after=after)

    def say(
        self, text: str, *, seconds: float | None = None, after: Action | None = None
    ) -> Action:
        """Show speech captured now; omit seconds to persist, or wait then clear this occurrence.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _Say, _schedule

        return _schedule(self, _Say(text, seconds=seconds), after=after)

    def think(
        self, text: str, *, seconds: float | None = None, after: Action | None = None
    ) -> Action:
        """Show thought captured now; timed dialogue waits using the simulation clock.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _schedule, _Think

        return _schedule(self, _Think(text, seconds=seconds), after=after)

    def clear_bubble(self, *, after: Action | None = None) -> Action:
        """Clear speech or thought when reached, interrupting any timed bubble writer.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _ClearBubble, _schedule

        return _schedule(self, _ClearBubble(), after=after)

    def play_sound(
        self, sound: Sound, *, volume: float = 1, wait: bool = True, after: Action | None = None
    ) -> Action:
        """Play one sound occurrence; by default wait for its channel to finish.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _PlaySound, _schedule

        return _schedule(self, _PlaySound(sound, volume=volume, wait=wait), after=after)

    def call(self, function: Callable[[], None | Action], *, after: Action | None = None) -> Action:
        """Run a typed function when reached; wait for its returned Action, if any.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _Call, _schedule

        return _schedule(self, _Call(function), after=after)

    def set_pose(self, pose: Pose, *, after: Action | None = None) -> Action:
        """Set a complete pose belonging to this Puppet skeleton.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _schedule, _SetPose

        return _schedule(self, _SetPose(pose), after=after)

    def poses(self, poses: Iterable[Pose], *, fps: float, after: Action | None = None) -> Action:
        """Interpolate adjacent poses at fps; repeat the first pose to author a closing transition.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _Poses, _schedule

        return _schedule(self, _Poses(poses, fps=fps), after=after)

    def set_part_costume(
        self, joint: str, costume: CostumeSource, *, after: Action | None = None
    ) -> Action:
        """Replace an existing attachment without changing topology or interrupting pose motion.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _schedule, _SetPartCostume

        return _schedule(self, _SetPartCostume(joint, costume), after=after)

    def sequence(self) -> PuppetGroup:
        """Create a one-pass recipe; recording commands does not execute them."""
        from .groups import PuppetGroup

        return PuppetGroup(self)

    def repeat(self, times: int | None = None) -> PuppetGroup:
        """Create a repeated recipe; omit times to repeat until canceled."""
        from .groups import PuppetGroup

        return PuppetGroup(self, times)

    def act(self, group: PuppetGroup, *, after: Action | None = None) -> Action:
        """Schedule a fresh snapshot of this actor's recipe. Later edits are independent."""
        from ._commands import _schedule
        from .groups import _snapshot

        return _schedule(self, _snapshot(group, self), after=after)

    def during(
        self, foreground: PuppetGroup, *, meanwhile: PuppetGroup, after: Action | None = None
    ) -> Action:
        """Run recipes together, canceling the background when foreground finishes."""
        from ._commands import _DuringPlan, _schedule
        from .groups import _snapshot

        return _schedule(
            self,
            _DuringPlan(_snapshot(foreground, self), background=_snapshot(meanwhile, self)),
            after=after,
        )

    def stop(self, action: Action | None = None) -> None:
        """Cancel this actor's owned executions; registrations remain available."""
        from ._scripts import _stop_actor

        _stop_actor(self, action)

    @property
    def rotation_style(self) -> RotationStyle:
        """Visual rotation only; movement always follows direction."""
        return self._rotation_style

    @rotation_style.setter
    def rotation_style(self, value: RotationStyle) -> None:
        if not isinstance(value, RotationStyle):
            raise TypeError("Use a RotationStyle value")
        self._rotation_style = value


def _bounds(actor: Puppet, direction: float) -> Bounds:
    points: list[Point] = []
    pivots = _pivots(actor.pose)
    for name, costume in actor._parts.items():
        (px, py), angle = pivots[name]
        ax, ay = costume.anchor
        for x in (0, costume.width):
            for y in (0, costume.height):
                dx, dy = _rotate((x - ax, ay - y), angle + 90)
                local = (px + dx, py + dy)
                if _mirrored(direction, actor.rotation_style):
                    local = (-local[0], local[1])
                dx, dy = _rotate(
                    local, _visual_direction(direction, actor.rotation_style), actor.scale
                )
                points.append((actor.x + dx, actor.y + dy))
    return Bounds(
        min(p[0] for p in points),
        min(p[1] for p in points),
        max(p[0] for p in points),
        max(p[1] for p in points),
    )


def _stick_figure(color: Color, stroke_width: float) -> Puppet:
    from math import ceil, floor

    import pygame
    from PIL import Image, ImageDraw

    width = _positive(stroke_width, "stroke_width")
    rgba = tuple(pygame.Color(color))
    skeleton = Skeleton.human()
    parts: dict[str, CostumeSource] = {}
    for name in skeleton.joints:
        ends = [joint.offset for joint in skeleton.joints.values() if joint.parent == name]
        radius = 10.0 if name == HumanJoint.HEAD else width / 2
        if not ends and name != HumanJoint.HEAD:
            continue
        points = [(0.0, 0.0), *ends]
        left = floor(min(x for x, _ in points) - radius)
        top = ceil(max(y for _, y in points) + radius)
        right = ceil(max(x for x, _ in points) + radius)
        bottom = floor(min(y for _, y in points) - radius)
        image = Image.new("RGBA", (max(1, right - left + 1), max(1, top - bottom + 1)))
        draw = ImageDraw.Draw(image)
        for x, y in ends:
            draw.line([(-left, top), (x - left, top - y)], fill=rgba, width=max(1, round(width)))
        for x, y in points:
            r = radius if name == HumanJoint.HEAD else width / 2
            draw.ellipse((x - left - r, top - y - r, x - left + r, top - y + r), fill=rgba)
        parts[name] = Costume(image, anchor=(-left, top))
    return Puppet(skeleton, parts=parts)
