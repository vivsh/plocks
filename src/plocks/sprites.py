"""Moving image sprites; transforms own no synchronized rectangle state."""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Iterable
from typing import TYPE_CHECKING, TypeVar, cast, overload

from ._operations import _CostumeRun, _sample_costume
from ._scripts import WhenBusy, _conflicts
from .actions import Action
from .audio import Sound
from .geometry import Bounds, Point, _integer, _number, _Placement, _point, _positive, _rotate
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

if TYPE_CHECKING:
    from ._commands import Actor, _Say, _Think
    from ._operations import _BubbleRun
    from .groups import SpriteGroup
    from .puppets import Puppet
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


class Sprite:
    """A movable image. Construct it, then add it with stage.add(sprite).

    Positions use logical pixels and the costume anchor. Commands schedule Actions;
    property assignments apply immediately. Direction 90 faces right.
    """

    __slots__ = (
        "_bubble",
        "_layer",
        "_rotation_style",
        "_scale",
        "_stage",
        "_transform",
        "_visible",
        "_visual",
    )

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
    ) -> None:
        self._transform: _Placement | Body = _Placement(
            (_number(x, "x"), _number(y, "y")), _number(direction, "direction") % 360, body_type
        )
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
    def on_click(self, work: SpriteGroup, *, when_busy: WhenBusy = WhenBusy.IGNORE) -> None: ...
    def on_click(self, work: object, *, when_busy: WhenBusy = WhenBusy.IGNORE) -> object:
        """Bind a recipe or decorate a click callback for this topmost visible actor."""
        from .stage import _attached

        return _attached(self)._on_actor_click(self, work, when_busy)

    @overload
    def on_start(self, work: _P) -> _P: ...
    @overload
    def on_start(self, work: SpriteGroup) -> None: ...
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
        self, key: Key, group: SpriteGroup, *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> None: ...
    def on_key_down(
        self, key: Key, group: SpriteGroup | None = None, *, when_busy: WhenBusy = WhenBusy.IGNORE
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
        group: SpriteGroup,
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None: ...
    def on_message(
        self,
        message: Signal | Message[_D],
        group: SpriteGroup | None = None,
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

    def set_costume(self, costume: CostumeSource, *, after: Action | None = None) -> Action:
        """Snapshot an image now and display it when reached.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _schedule, _SetCostume

        return _schedule(self, _SetCostume(costume), after=after)

    def costumes(
        self, frames: Iterable[CostumeSource], *, fps: float, after: Action | None = None
    ) -> Action:
        """Play one costume pass at fps, including the final frame interval.

        Returns immediately. Use after to sequence; awaiting observes this execution.
        """
        from ._commands import _Costumes, _schedule

        return _schedule(self, _Costumes(frames, fps=fps), after=after)

    def sequence(self) -> SpriteGroup:
        """Create a one-pass recipe; recording commands does not execute them."""
        from .groups import SpriteGroup

        return SpriteGroup(self)

    def repeat(self, times: int | None = None) -> SpriteGroup:
        """Create a repeated recipe; omit times to repeat until canceled."""
        from .groups import SpriteGroup

        return SpriteGroup(self, times)

    def act(self, group: SpriteGroup, *, after: Action | None = None) -> Action:
        """Schedule a fresh snapshot of this actor's recipe. Later edits are independent."""
        from ._commands import _schedule
        from .groups import _snapshot

        return _schedule(self, _snapshot(group, self), after=after)

    def during(
        self, foreground: SpriteGroup, *, meanwhile: SpriteGroup, after: Action | None = None
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
