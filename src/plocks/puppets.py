"""Articulated image actors with immutable skeletons and one current pose."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Generic, Self, TypeVar, cast, overload

from typing_extensions import deprecated

from ._operations import _PoseRun, _sample_pose
from ._scripts import WhenBusy, _conflicts
from .actions import Action
from .audio import Sound
from .events import Click, Event, GamepadPress, GamepadRelease
from .gamepads import Gamepad, GamepadButton
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
from .imaging import Image, ImageSource, _image
from .messages import Message
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
from .state import _new_state, _State_co

if TYPE_CHECKING:
    from ._commands import Actor, _Say, _Think
    from ._operations import _BubbleRun
    from .scripts import Script
    from .sprites import Sprite
    from .stage import Stage
    from .tiling import TileMap


_D = TypeVar("_D")
_Other = TypeVar("_Other", bound="Sprite | Puppet | TileMap")
_R = TypeVar("_R", bound="None | Action | Script[Puppet] | Script[Actor]")


class Puppet(Generic[_State_co]):  # noqa: UP046 -- default state type supports Python 3.12
    """An articulated image actor. Construct it, then add it with stage.add(puppet).

    Positions use logical pixels and the image anchor. Commands schedule Actions;
    property assignments apply immediately. Direction 90 faces right.

    Args:
        skeleton: The joints that connect the puppet's parts.
        parts: Images attached to joints, keyed by joint name.
        pose: Starting joint positions; omit to use the skeleton's rest pose.
        body_type: How the puppet behaves when stage physics is enabled.
        state: A dataclass type for this puppet's state, if needed.
    """

    __slots__ = (
        "_bubble",
        "_is_clone",
        "_layer",
        "_parts",
        "_pose",
        "_rotation_style",
        "_scale",
        "_skeleton",
        "_stage",
        "_state",
        "_transform",
        "_visible",
    )

    @overload
    def __init__(
        self: Puppet[None],
        skeleton: Skeleton,
        *,
        parts: Mapping[str, ImageSource],
        pose: Pose | None = None,
        body_type: BodyType = BodyType.DYNAMIC,
        state: None = None,
    ) -> None: ...
    @overload
    def __init__(
        self,
        skeleton: Skeleton,
        *,
        parts: Mapping[str, ImageSource],
        pose: Pose | None = None,
        body_type: BodyType = BodyType.DYNAMIC,
        state: type[_State_co],
    ) -> None: ...
    def __init__(
        self,
        skeleton: Skeleton,
        *,
        parts: Mapping[str, ImageSource],
        pose: Pose | None = None,
        body_type: BodyType = BodyType.DYNAMIC,
        state: type[object] | None = None,
    ) -> None:
        self._state: _State_co = cast(_State_co, _new_state(state))
        if not parts or any(name not in skeleton.joints for name in parts):
            raise ValueError("Supply at least one image part on existing joints")
        self._skeleton = skeleton
        self._parts = {name: _image(source) for name, source in parts.items()}
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
        self._is_clone = False
        self._bubble: _Say | _Think | _BubbleRun | None = None

    @property
    def is_clone(self) -> bool:
        """Whether this actor was created by clone(); removal does not change it."""
        return self._is_clone

    def clone(self) -> Puppet[_State_co]:
        """Add an independent copy to the same stage and queue its clone-start event.

        The returned actor is already added: do not call stage.add(copy).
        Set copy.position or other properties directly after clone().

        Copy current transforms and appearance, shallow-copy dataclass state, and
        inherit actor-bound controls and handlers. Nested state values and immutable
        assets are shared. Running actions, bubbles and voices are not copied.
        Physics configuration is copied into a new body with zero initial velocity.
        Clone-start handlers run later, allowing position changes before they start.

        Raises StageError when detached, closed, or the 300-clone limit is reached.
        Custom actor subclasses must implement their own factory. State-copy failures
        retain their original exception. Removing a clone retires its registrations.
        """
        from ._cloning import _clone

        return cast("Puppet[_State_co]", _clone(self))

    @overload
    def on_clone(
        self, work: Callable[[Event[Self, None]], _R]
    ) -> Callable[[Event[Self, None]], _R]: ...
    @overload
    def on_clone(self, work: Script[Puppet] | Script[Actor]) -> None: ...
    def on_clone(self, work: object) -> object:
        """Bind a script or callback(event) to each newly created clone.

        event.target is the new clone, event.source is the actor it copied, and
        event.data is None. Use event.target in inherited handlers. Attach before
        registering. Each clone inherits a snapshot of existing registrations.
        """
        from .stage import _attached

        return _attached(self)._on_actor_clone(self, work)

    @property
    def state(self) -> _State_co:
        """This owner's dataclass instance, or None when state was not supplied.

        The association is read-only; its fields follow ordinary Python behavior.
        Constructors create an instance; clone() shallow-copies its current values.
        Values survive removal and closure.
        """
        return self._state

    @property
    def skeleton(self) -> Skeleton:
        """Immutable topology; poses must reference this exact instance."""
        return self._skeleton

    @property
    def parts(self) -> Mapping[str, Image]:
        """Read-only image attachments in painting order; keys remain fixed."""
        return MappingProxyType(self._parts)

    @staticmethod
    def stick_figure(*, color: Color = "white", stroke_width: float = 4.0) -> Puppet[None]:
        """Create a human Puppet using generated capsule/disc images; no files needed."""
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
        """The same coordinates as (x, y), measured at the image anchor."""
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
        previous = self._pose
        self._pose = value
        try:
            from ._physics import _sync_shape

            _sync_shape(self)
        except BaseException:
            self._pose = previous
            raise

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

    @overload
    def on_touch(
        self, other: _Other, *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> Callable[[Callable[[Event[Self, _Other]], _R]], Callable[[Event[Self, _Other]], _R]]: ...
    @overload
    def on_touch(
        self,
        other: Sprite | Puppet | TileMap,
        script: Script[Puppet] | Script[Actor],
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None: ...
    def on_touch(
        self,
        other: Sprite | Puppet | TileMap,
        script: Script[Puppet] | Script[Actor] | None = None,
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> object:
        """Bind a Script or callback(event) when AABB overlap begins.

        event.data is the other object; event.target is this receiver. Samples
        follow simulation steps, including hidden actors. Removal is not a leave
        event. Pause freezes sampling; fast between-tick crossings may be missed.
        """
        from ._touches import _bind

        return _bind(self, other, script, False, when_busy)

    @overload
    def on_touch_end(
        self, other: _Other, *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> Callable[[Callable[[Event[Self, _Other]], _R]], Callable[[Event[Self, _Other]], _R]]: ...
    @overload
    def on_touch_end(
        self,
        other: Sprite | Puppet | TileMap,
        script: Script[Puppet] | Script[Actor],
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None: ...
    def on_touch_end(
        self,
        other: Sprite | Puppet | TileMap,
        script: Script[Puppet] | Script[Actor] | None = None,
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> object:
        """Bind a Script or callback(event) when AABB overlap ends.

        event.data is the other object; event.target is this receiver. Samples
        follow simulation steps, including hidden actors. Removal is not a leave
        event. Pause freezes sampling; fast between-tick crossings may be missed.
        """
        from ._touches import _bind

        return _bind(self, other, script, True, when_busy)

    def on_update(
        self, callback: Callable[[Event[Self, float]], None]
    ) -> Callable[[Event[Self, float]], None]:
        """Register synchronous callback(event) in fixed simulation seconds.

        Runs while attached, including when hidden; pause stops updates.
        Must return None. Use a Script for timed reusable behavior.
        """
        from .stage import _attached

        _attached(self)._on_actor_update(self, callback)
        return callback

    @overload
    def on_start(
        self, work: Callable[[Event[Self, None]], _R]
    ) -> Callable[[Event[Self, None]], _R]: ...
    @overload
    def on_start(self, work: Script[Puppet] | Script[Actor]) -> None: ...
    def on_start(self, work: object) -> object:
        """Bind startup Script or callback(event); attach before registering."""
        from .stage import _attached

        return _attached(self)._on_actor_start(self, work)

    @overload
    def on_click(
        self, work: Callable[[Event[Self, Click]], _R], *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> Callable[[Event[Self, Click]], _R]: ...
    @overload
    def on_click(
        self, work: Script[Puppet] | Script[Actor], *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> None: ...
    def on_click(self, work: object, *, when_busy: WhenBusy = WhenBusy.IGNORE) -> object:
        """Bind topmost-hit click Script or callback(event).

        event.data is (stage_position, button). Returning Script/Action keeps
        this registration busy until completion. Default repeated clicks ignore.
        """
        from .stage import _attached

        return _attached(self)._on_actor_click(self, work, when_busy)

    @overload
    def on_button_down(
        self,
        button: GamepadButton,
        *,
        gamepad: Gamepad | None = None,
        repeat: float | None = None,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> Callable[
        [Callable[[Event[Self, GamepadPress]], _R]], Callable[[Event[Self, GamepadPress]], _R]
    ]: ...
    @overload
    def on_button_down(
        self,
        button: GamepadButton,
        script: Script[Puppet] | Script[Actor],
        *,
        gamepad: Gamepad | None = None,
        repeat: float | None = None,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None: ...
    def on_button_down(
        self,
        button: GamepadButton,
        script: Script[Puppet] | Script[Actor] | None = None,
        *,
        gamepad: Gamepad | None = None,
        repeat: float | None = None,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> object:
        """React to a logical press; optional repeat uses simulation seconds.

        Filter by a stage.gamepads slot for local multiplayer. Event.data contains
        gamepad and button. A script executes independently on this receiver.

        Args:
            button: The button to listen for.
            script: A script to run; omit it to decorate a function.
            gamepad: Listen to one player; omit to listen to all players.
            repeat: Seconds between repeated presses while held; omit for one press.
            when_busy: What to do if the previous script is still running.
        """
        from .stage import _attached, _gamepad_selection, _repeat_interval

        stage = _attached(self)
        repeat = _repeat_interval(repeat)
        _gamepad_selection(stage, button, gamepad)
        if script is not None:
            return stage.on_button_down(
                button, self, script, gamepad=gamepad, repeat=repeat, when_busy=when_busy
            )
        return stage._gamepad_decorator(button, self, gamepad, repeat, when_busy)

    @overload
    def on_button_up(
        self,
        button: GamepadButton,
        *,
        gamepad: Gamepad | None = None,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> Callable[
        [Callable[[Event[Self, GamepadRelease]], _R]], Callable[[Event[Self, GamepadRelease]], _R]
    ]: ...
    @overload
    def on_button_up(
        self,
        button: GamepadButton,
        script: Script[Puppet] | Script[Actor],
        *,
        gamepad: Gamepad | None = None,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None: ...
    def on_button_up(
        self,
        button: GamepadButton,
        script: Script[Puppet] | Script[Actor] | None = None,
        *,
        gamepad: Gamepad | None = None,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> object:
        """React once when a logical button is released; event.data identifies its player.

        Args:
            button: The button to listen for.
            script: A script to run; omit it to decorate a function.
            gamepad: Listen to one player; omit to listen to all players.
            when_busy: What to do if the previous script is still running.
        """
        from .stage import _attached, _gamepad_selection

        stage = _attached(self)
        _gamepad_selection(stage, button, gamepad)
        if script is not None:
            return stage.on_button_up(button, self, script, gamepad=gamepad, when_busy=when_busy)
        return stage._gamepad_up_decorator(button, self, gamepad, when_busy)

    @overload
    def on_broadcast(
        self, message: Message[_D], *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> Callable[[Callable[[Event[Self, _D]], _R]], Callable[[Event[Self, _D]], _R]]: ...
    @overload
    def on_broadcast(
        self,
        message: Message[_D],
        script: Script[Puppet] | Script[Actor],
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None: ...
    def on_broadcast(
        self,
        message: Message[_D],
        script: Script[Puppet] | Script[Actor] | None = None,
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> object:
        """Receive a typed Event through callback(event) or Script.

        event.target is the receiver; event.source is the sender. Direct
        Script bindings ignore payload. Only accepted invocations evaluate work.
        """
        from .stage import _attached

        stage = _attached(self)
        if script is not None:
            return stage.on_broadcast(message, self, script, when_busy=when_busy)
        return stage._message_decorator(cast(Message[object], message), self, when_busy)

    def move(self, steps: float, *, after: Action | None = None) -> Action:
        """Move along direction in logical pixels when reached.

        Returns immediately. Use after to sequence; inspect the returned Action for completion.

        Args:
            steps: How far to move in the current direction, in pixels.
            after: Wait for this Action before moving.
        """
        from ._commands import _Move, _schedule

        return _schedule(self, _Move(steps), after=after)

    def move_to(
        self, *, x: float | None = None, y: float | None = None, after: Action | None = None
    ) -> Action:
        """Set supplied world coordinates when reached; omitted axes stay unchanged.

        Returns immediately. Use after to sequence; inspect the returned Action for completion.

        Args:
            x: The new world x coordinate; omit to leave x unchanged.
            y: The new world y coordinate; omit to leave y unchanged.
            after: Wait for this Action before moving.
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
        """Glide to a place in your world while the game keeps running.

        Args:
            x: Destination x in world pixels; leave out to keep x free.
            y: Destination y in world pixels; leave out to keep y free.
            seconds: How long the glide takes in game time.
            easing: How the glide speeds up or slows down; default is steady.
            after: Wait for this Action before starting the glide.

        Use a nonphysical or kinematic actor; dynamic bodies move using physics.
        """
        from ._commands import _GlideTo, _schedule

        return _schedule(self, _GlideTo(x=x, y=y, seconds=seconds, easing=easing), after=after)

    def follow_path(
        self, points: Iterable[Point], *, speed: float = 100, after: Action | None = None
    ) -> Action:
        """Schedule world waypoints at speed pixels/second using existing glides.

        Points snapshot now; movement begins when reached. Both axes are claimed.
        Pause/cancellation follow normal movement rules. This does not replan or
        detect newly edited walls; dynamic physical actors cannot use glides.
        """
        from ._commands import _FollowPath, _schedule

        return _schedule(self, _FollowPath(points, speed=speed), after=after)

    def glide_by(
        self,
        *,
        x: float | None = None,
        y: float | None = None,
        seconds: float,
        easing: Ease = Ease.LINEAR,
        after: Action | None = None,
    ) -> Action:
        """Glide by a distance while the rest of the game keeps running.

        Args:
            x: Pixels to move right; use a negative number to move left.
            y: Pixels to move up; use a negative number to move down.
            seconds: How long the glide takes in game time.
            easing: How the glide speeds up or slows down; default is steady.
            after: Wait for this Action before starting the glide.

        Leave out an axis to keep it free. Use a nonphysical or kinematic actor;
        dynamic bodies move using physics. The starting place is taken at start.
        """
        from ._commands import _GlideBy, _schedule

        return _schedule(self, _GlideBy(x=x, y=y, seconds=seconds, easing=easing), after=after)

    def wait(self, seconds: float, *, after: Action | None = None) -> Action:
        """Wait simulated seconds; pause freezes progress and zero yields one tick.

        Returns immediately. Use after to sequence; inspect the returned Action for completion.
        """
        from ._commands import _schedule, _Wait

        return _schedule(self, _Wait(seconds), after=after)

    def turn_left(self, degrees: float, *, after: Action | None = None) -> Action:
        """Turn counterclockwise by degrees when reached.

        Returns immediately. Use after to sequence; inspect the returned Action for completion.
        """
        from ._commands import _schedule, _TurnLeft

        return _schedule(self, _TurnLeft(degrees), after=after)

    def turn_right(self, degrees: float, *, after: Action | None = None) -> Action:
        """Turn clockwise by degrees when reached.

        Returns immediately. Use after to sequence; inspect the returned Action for completion.
        """
        from ._commands import _schedule, _TurnRight

        return _schedule(self, _TurnRight(degrees), after=after)

    def point_towards(self, target: Point | Actor, *, after: Action | None = None) -> Action:
        """Face a world point or the target actor position sampled when reached.

        Returns immediately. Use after to sequence; inspect the returned Action for completion.
        """
        from ._commands import _PointTowards, _schedule

        return _schedule(self, _PointTowards(target), after=after)

    def go_to_random(self, bounds: Bounds | None = None, *, after: Action | None = None) -> Action:
        """Choose an anchor position uniformly in bounds, or the visible world.

        Returns immediately. Use after to sequence; inspect the returned Action for completion.
        """
        from ._commands import _GoToRandom, _schedule

        return _schedule(self, _GoToRandom(bounds), after=after)

    def bounce_on_edge(
        self, bounds: Bounds | None = None, *, after: Action | None = None
    ) -> Action:
        """Fit within bounds and reflect outward motion; oversized actors raise ValueError.

        Returns immediately. Use after to sequence; inspect the returned Action for completion.
        """
        from ._commands import _BounceOnEdge, _schedule

        return _schedule(self, _BounceOnEdge(bounds), after=after)

    def say(
        self, text: str, *, seconds: float | None = None, after: Action | None = None
    ) -> Action:
        """Show speech captured now; omit seconds to persist, or wait then clear this occurrence.

        Returns immediately. Use after to sequence; inspect the returned Action for completion.

        Args:
            text: The words to show, captured when this method is called.
            seconds: How long to show the bubble; omit to keep it visible.
            after: Wait for this Action before showing the bubble.
        """
        from ._commands import _Say, _schedule

        return _schedule(self, _Say(text, seconds=seconds), after=after)

    def think(
        self, text: str, *, seconds: float | None = None, after: Action | None = None
    ) -> Action:
        """Show thought captured now; timed dialogue waits using the simulation clock.

        Returns immediately. Use after to sequence; inspect the returned Action for completion.

        Args:
            text: The words to show, captured when this method is called.
            seconds: How long to show the bubble; omit to keep it visible.
            after: Wait for this Action before showing the bubble.
        """
        from ._commands import _schedule, _Think

        return _schedule(self, _Think(text, seconds=seconds), after=after)

    def clear_bubble(self, *, after: Action | None = None) -> Action:
        """Clear speech or thought when reached, interrupting any timed bubble writer.

        Returns immediately. Use after to sequence; inspect the returned Action for completion.
        """
        from ._commands import _ClearBubble, _schedule

        return _schedule(self, _ClearBubble(), after=after)

    def play_sound(
        self, sound: Sound, *, volume: float = 1, wait: bool = True, after: Action | None = None
    ) -> Action:
        """Play one sound occurrence; by default wait for its channel to finish.

        Returns immediately. Use after to sequence; inspect the returned Action for completion.
        """
        from ._commands import _PlaySound, _schedule

        return _schedule(self, _PlaySound(sound, volume=volume, wait=wait), after=after)

    def set_pose(self, pose: Pose, *, after: Action | None = None) -> Action:
        """Set a complete pose belonging to this Puppet skeleton.

        Returns immediately. Use after to sequence; inspect the returned Action for completion.
        """
        from ._commands import _schedule, _SetPose

        return _schedule(self, _SetPose(pose), after=after)

    def poses(self, poses: Iterable[Pose], *, fps: float, after: Action | None = None) -> Action:
        """Interpolate adjacent poses at fps; repeat the first pose to author a closing transition.

        Returns immediately. Use after to sequence; inspect the returned Action for completion.
        """
        from ._commands import _Poses, _schedule

        return _schedule(self, _Poses(poses, fps=fps), after=after)

    def set_part_image(
        self, joint: str, image: ImageSource, *, after: Action | None = None
    ) -> Action:
        """Replace an existing attachment without changing topology or interrupting pose motion.

        Returns immediately. Use after to sequence; inspect the returned Action for completion.
        """
        from ._commands import _schedule, _SetPartImage

        return _schedule(self, _SetPartImage(joint, image), after=after)

    @deprecated("set_part_costume is deprecated; use set_part_image")
    def set_part_costume(
        self, joint: str, costume: ImageSource, *, after: Action | None = None
    ) -> Action:
        """Deprecated alias for set_part_image; changes the same attachment."""
        return self.set_part_image(joint, costume, after=after)

    def sequence(self) -> Script[Puppet]:
        """Create an empty reusable Script with this actor's capabilities.

        Does not bind this actor, require stage membership, or schedule work.
        Record commands, then pass the script to act() or an event registration.
        Other compatible actors can share it with independent progress.
        """
        from .scripts import Script

        return Script(Puppet)

    def repeat(self, times: int | None = None) -> Script[Puppet]:
        """Create a reusable Script repeated times, or indefinitely when omitted.

        Only records a definition; call act() to start it on a compatible actor.
        times must be a nonnegative integer, excluding bool. Empty indefinite
        scripts must receive commands before execution.
        """
        return self.sequence().repeat(times)

    def act(self, script: Script[Puppet] | Script[Actor], *, after: Action | None = None) -> Action:
        """Admit a fresh Script snapshot on this actor; return its Action.

        Requires stage membership. Effects start in the next eligible phase.
        Shared definitions have independent progress; later edits do not alter it.

        Args:
            script: The script to start on this actor.
            after: Wait for this Action before starting the script.
        """
        from ._commands import _schedule
        from .scripts import _snapshot

        receiver: Puppet = self
        plan = _snapshot(script, receiver)
        return _schedule(self, plan, after=after)

    @overload
    def broadcast(
        self,
        message: Message[None],
        *,
        to: Actor | None = None,
        wait: bool = False,
        after: Action | None = None,
    ) -> Action: ...
    @overload
    def broadcast(
        self,
        message: Message[_D],
        data: _D,
        *,
        to: Actor | None = None,
        wait: bool = False,
        after: Action | None = None,
    ) -> Action: ...
    def broadcast(
        self,
        message: Message[_D],
        data: _D | None = None,
        *,
        to: Actor | None = None,
        wait: bool = False,
        after: Action | None = None,
    ) -> Action:
        """Schedule a message from this actor; to selects a receiver, wait joins it.

        With no destination, all matching stage registrations receive it FIFO.
        Payload is captured by reference; cancellation cannot retract a sent message.
        """
        from ._commands import _schedule, _Send
        from .scripts import _message_arguments

        _message_arguments(message, to, wait)
        return _schedule(self, _Send(cast(Message[object], message), data, to, wait), after=after)

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
    for name, image in actor._parts.items():
        (px, py), angle = pivots[name]
        ax, ay = image.anchor
        for x in (0, image.width):
            for y in (0, image.height):
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


def _stick_figure(color: Color, stroke_width: float) -> Puppet[None]:
    from math import ceil, floor

    import pygame
    from PIL import Image as PillowImage
    from PIL import ImageDraw

    width = _positive(stroke_width, "stroke_width")
    rgba = tuple(pygame.Color(color))
    skeleton = Skeleton.human()
    parts: dict[str, ImageSource] = {}
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
        image = PillowImage.new("RGBA", (max(1, right - left + 1), max(1, top - bottom + 1)))
        draw = ImageDraw.Draw(image)
        for x, y in ends:
            draw.line([(-left, top), (x - left, top - y)], fill=rgba, width=max(1, round(width)))
        for x, y in points:
            r = radius if name == HumanJoint.HEAD else width / 2
            draw.ellipse((x - left - r, top - y - r, x - left + r, top - y + r), fill=rgba)
        parts[name] = Image(image, anchor=(-left, top))
    return Puppet(skeleton, parts=parts)
