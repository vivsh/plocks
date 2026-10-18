"""Moving image sprites; transforms own no synchronized rectangle state."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Generic, Self, TypeVar, cast, overload

from ._operations import _CostumeRun, _sample_costume
from ._scripts import WhenBusy, _conflicts
from .actions import Action
from .audio import Sound
from .events import Click, Event, GamepadPress
from .gamepads import Gamepad, GamepadButton
from .geometry import Bounds, Point, _integer, _number, _Placement, _point, _positive, _rotate
from .imaging import Costume, CostumeSource, _costume
from .input import Key
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
from .state import _new_state, _State_co

if TYPE_CHECKING:
    from ._commands import Actor, _Say, _Think
    from ._operations import _BubbleRun
    from .puppets import Puppet
    from .scripts import Script
    from .stage import Stage
    from .tiling import TileMap


_D = TypeVar("_D")
_R = TypeVar("_R", bound="None | Action | Script[Sprite] | Script[Actor]")


class Sprite(Generic[_State_co]):  # noqa: UP046 -- default state type supports Python 3.12
    """A movable image. Construct it, then add it with stage.add(sprite).

    Positions use logical pixels and the costume anchor. Commands schedule Actions;
    property assignments apply immediately. Direction 90 faces right.
    one_way=True makes a horizontal static/kinematic platform with a top-only
    physical edge; its default False keeps ordinary full-shape collision.
    """

    __slots__ = (
        "_bubble",
        "_layer",
        "_one_way",
        "_rotation_style",
        "_scale",
        "_stage",
        "_state",
        "_transform",
        "_visible",
        "_visual",
    )

    @overload
    def __init__(
        self: Sprite[None],
        source: CostumeSource,
        *,
        x: float = 0,
        y: float = 0,
        direction: float = 90,
        scale: float = 1,
        visible: bool = True,
        layer: int = 0,
        body_type: BodyType = BodyType.DYNAMIC,
        one_way: bool = False,
        state: None = None,
    ) -> None: ...
    @overload
    def __init__(
        self,
        source: CostumeSource,
        *,
        x: float = 0,
        y: float = 0,
        direction: float = 90,
        scale: float = 1,
        visible: bool = True,
        layer: int = 0,
        body_type: BodyType = BodyType.DYNAMIC,
        one_way: bool = False,
        state: type[_State_co],
    ) -> None: ...
    def __init__(
        self,
        source: CostumeSource,
        *,
        x: float = 0,
        y: float = 0,
        direction: float = 90,
        scale: float = 1,
        visible: bool = True,
        layer: int = 0,
        body_type: BodyType = BodyType.DYNAMIC,
        one_way: bool = False,
        state: type[object] | None = None,
    ) -> None:
        self._state: _State_co = cast(_State_co, _new_state(state))
        self._transform: _Placement | Body = _Placement(
            (_number(x, "x"), _number(y, "y")), _number(direction, "direction") % 360, body_type
        )
        if not isinstance(one_way, bool):
            raise TypeError("one_way must be bool")
        if one_way and body_type not in (BodyType.STATIC, BodyType.KINEMATIC):
            raise ValueError("A one-way platform must be static or kinematic")
        if one_way and self._transform.direction != 90:
            raise ValueError("A one-way platform must be horizontal (direction=90)")
        self._one_way = one_way
        self._scale = _positive(scale, "scale")
        self._visible = visible
        self._layer = _integer(layer, "layer")
        self._visual: Costume | _CostumeRun = _costume(source)
        if not isinstance(body_type, BodyType):
            raise TypeError("Use a BodyType value")
        self._stage: Stage | None = None
        self._rotation_style = RotationStyle.ALL_AROUND
        self._bubble: _Say | _Think | _BubbleRun | None = None

    @property
    def state(self) -> _State_co:
        """This owner's dataclass instance, or None when state was not supplied.

        The association is read-only; its fields follow ordinary Python behavior.
        Each owner constructs its own instance. Values survive removal and closure.
        """
        return self._state

    @property
    def body(self) -> Body:
        """Current physical attachment; raises PhysicsError when detached or physics is off."""
        from .errors import PhysicsError

        if not isinstance(self._transform, Body):
            raise PhysicsError("Add this actor to Stage(physics=True) with a physical body_type")
        return self._transform

    @property
    def one_way(self) -> bool:
        """Whether this static/kinematic Box platform supports landing from above only.

        Read-only construction setting. Jump through from below; side passage is
        allowed. Physics requires Stage(physics=True); artwork remains unchanged.
        One-way platforms stay horizontal and cannot use Circle collision shapes.
        """
        return self._one_way

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
        if self.one_way and value not in (BodyType.STATIC, BodyType.KINEMATIC):
            raise ValueError("A one-way platform must be static or kinematic")
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
    def costume(self) -> Costume:
        """The current immutable image; assigning it stops costume animation."""
        if isinstance(self._visual, _CostumeRun):
            assert self._stage is not None
            return _sample_costume(self._visual, self._stage.time)
        return self._visual

    @costume.setter
    def costume(self, value: CostumeSource) -> None:
        costume = _costume(value)
        _conflicts(self, False, False, visual=True)
        self._visual = costume

    @property
    def bounds(self) -> Bounds:
        """Derived world AABB, including transparent pixels and transformations."""
        costume = self.costume
        ax, ay = costume.anchor
        corners = [
            _rotate(
                (
                    -(cx - ax) if _mirrored(self.direction, self.rotation_style) else cx - ax,
                    ay - cy,
                ),
                _visual_direction(self.direction, self.rotation_style),
                self.scale,
            )
            for cx in (0, costume.width)
            for cy in (0, costume.height)
        ]
        return Bounds(
            self.x + min(p[0] for p in corners),
            self.y + min(p[1] for p in corners),
            self.x + max(p[0] for p in corners),
            self.y + max(p[1] for p in corners),
        )

    def touching(self, other: Sprite | Puppet | TileMap) -> bool:
        """Test AABB overlap, or solid tile overlap. Visibility does not affect it."""
        from .tiling import TileMap

        if isinstance(other, TileMap):
            return bool(other.tiles_touching(self.bounds, solid_only=True))
        return self.bounds.intersects(other.bounds)

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
    def on_start(self, work: Script[Sprite] | Script[Actor]) -> None: ...
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
        self, work: Script[Sprite] | Script[Actor], *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> None: ...
    def on_click(self, work: object, *, when_busy: WhenBusy = WhenBusy.IGNORE) -> object:
        """Bind topmost-hit click Script or callback(event).

        event.data is (stage_position, button). Returning Script/Action keeps
        this registration busy until completion. Default repeated clicks ignore.
        """
        from .stage import _attached

        return _attached(self)._on_actor_click(self, work, when_busy)

    @overload
    def on_key_down(
        self, key: Key, *, repeat: float | None = None, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> Callable[[Callable[[Event[Self, Key]], _R]], Callable[[Event[Self, Key]], _R]]: ...
    @overload
    def on_key_down(
        self,
        key: Key,
        script: Script[Sprite] | Script[Actor],
        *,
        repeat: float | None = None,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None: ...
    def on_key_down(
        self,
        key: Key,
        script: Script[Sprite] | Script[Actor] | None = None,
        *,
        repeat: float | None = None,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> object:
        """Bind Script or callback(event) to a fresh key transition.

        Held movement belongs in update. event.data is Key; event.target is this actor. Returning a Script
        selects it for this actor; an Action observes already admitted work.
        """
        from .stage import _attached

        stage = _attached(self)
        if script is not None:
            return stage.on_key_down(key, self, script, repeat=repeat, when_busy=when_busy)
        return stage._key_decorator(key, self, when_busy, repeat)

    @overload
    def on_gamepad_button_down(
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
    def on_gamepad_button_down(
        self,
        button: GamepadButton,
        script: Script[Sprite] | Script[Actor],
        *,
        gamepad: Gamepad | None = None,
        repeat: float | None = None,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None: ...
    def on_gamepad_button_down(
        self,
        button: GamepadButton,
        script: Script[Sprite] | Script[Actor] | None = None,
        *,
        gamepad: Gamepad | None = None,
        repeat: float | None = None,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> object:
        """React to a logical press; optional repeat uses simulation seconds.

        Filter by a stage.gamepads slot for multiplayer. Event.data contains
        gamepad and button. A script executes independently on this receiver.
        """
        from .stage import _attached, _gamepad_selection, _repeat_interval

        stage = _attached(self)
        repeat = _repeat_interval(repeat)
        _gamepad_selection(stage, button, gamepad)
        if script is not None:
            return stage.on_gamepad_button_down(
                button, self, script, gamepad=gamepad, repeat=repeat, when_busy=when_busy
            )
        return stage._gamepad_decorator(button, self, gamepad, repeat, when_busy)

    @overload
    def on_broadcast(
        self, message: Message[_D], *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> Callable[[Callable[[Event[Self, _D]], _R]], Callable[[Event[Self, _D]], _R]]: ...
    @overload
    def on_broadcast(
        self,
        message: Message[_D],
        script: Script[Sprite] | Script[Actor],
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None: ...
    def on_broadcast(
        self,
        message: Message[_D],
        script: Script[Sprite] | Script[Actor] | None = None,
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
        """
        from ._commands import _Move, _schedule

        return _schedule(self, _Move(steps), after=after)

    def move_to(
        self, *, x: float | None = None, y: float | None = None, after: Action | None = None
    ) -> Action:
        """Set supplied world coordinates when reached; omitted axes stay unchanged.

        Returns immediately. Use after to sequence; inspect the returned Action for completion.
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

        Returns immediately. Use after to sequence; inspect the returned Action for completion.
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

        Returns immediately. Use after to sequence; inspect the returned Action for completion.
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
        """
        from ._commands import _Say, _schedule

        return _schedule(self, _Say(text, seconds=seconds), after=after)

    def think(
        self, text: str, *, seconds: float | None = None, after: Action | None = None
    ) -> Action:
        """Show thought captured now; timed dialogue waits using the simulation clock.

        Returns immediately. Use after to sequence; inspect the returned Action for completion.
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

    def set_costume(self, costume: CostumeSource, *, after: Action | None = None) -> Action:
        """Snapshot an image now and display it when reached.

        Returns immediately. Use after to sequence; inspect the returned Action for completion.
        """
        from ._commands import _schedule, _SetCostume

        return _schedule(self, _SetCostume(costume), after=after)

    @overload
    def costumes(
        self, frames: Iterable[CostumeSource], *, fps: float, after: Action | None = None
    ) -> Action: ...
    @overload
    def costumes(
        self,
        frames: Iterable[CostumeSource],
        *,
        durations: Iterable[float],
        after: Action | None = None,
    ) -> Action: ...
    def costumes(
        self,
        frames: Iterable[CostumeSource],
        *,
        fps: float | None = None,
        durations: Iterable[float] | None = None,
        after: Action | None = None,
    ) -> Action:
        """Play one frame pass using fps or per-frame durations in simulation seconds.

        Supply exactly one timing form. Every frame, including the final one,
        holds for its full positive duration. Sources/timings are snapshotted now.
        """
        from ._commands import _Costumes, _schedule

        return _schedule(self, _Costumes(frames, fps=fps, durations=durations), after=after)

    def sequence(self) -> Script[Sprite]:
        """Create an empty reusable Script with this actor's capabilities.

        Does not bind this actor, require stage membership, or schedule work.
        Record commands, then pass the script to act() or an event registration.
        Other compatible actors can share it with independent progress.
        """
        from .scripts import Script

        return Script(Sprite)

    def repeat(self, times: int | None = None) -> Script[Sprite]:
        """Create a reusable Script repeated times, or indefinitely when omitted.

        Only records a definition; call act() to start it on a compatible actor.
        times must be a nonnegative integer, excluding bool. Empty indefinite
        scripts must receive commands before execution.
        """
        return self.sequence().repeat(times)

    def act(self, script: Script[Sprite] | Script[Actor], *, after: Action | None = None) -> Action:
        """Admit a fresh Script snapshot on this actor; return its Action.

        Requires stage membership. Effects start in the next eligible phase.
        Shared definitions have independent progress; later edits do not alter it.
        """
        from ._commands import _schedule
        from .scripts import _snapshot

        receiver: Sprite = self
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
