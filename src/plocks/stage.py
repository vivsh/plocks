"""Explicit scene membership, event registration, and fixed-step execution."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Literal, TypeVar, cast, overload

import pygame

from ._commands import Actor
from ._operations import _Delivery
from ._scripts import WhenBusy, _admit, _detach, _Handler
from .actions import Action
from .audio import Sound, Voice, _play, _volume
from .canvas import Canvas
from .errors import StageError
from .geometry import Bounds, Color, Point, _integer, _point
from .groups import Group
from .input import Key, Keyboard, Mouse, MouseButton
from .messages import Message, Signal
from .physics import Physics
from .puppets import Puppet
from .sprites import Sprite
from .tiling import TiledBackground, TileMap

type _Update = Callable[[float], None]
_U = TypeVar("_U", bound=_Update)
type _Press = Callable[[], None | Action | Coroutine[object, object, None]]
_P = TypeVar("_P", bound=_Press)
type _Result = None | Action | Coroutine[object, object, None]
type _Click = Callable[[Point, MouseButton], _Result]
_C = TypeVar("_C", bound=_Click)
_T = TypeVar("_T", bound=Actor)
_D = TypeVar("_D")
_R = TypeVar("_R", bound=_Result)
type _Draw = Callable[["Canvas"], None]
type _InputEvent = Key | tuple[Point, MouseButton]
type _StageObject = Sprite | Puppet | TileMap | TiledBackground


class Stage:
    """A centered 2D world. Register callbacks, then end your script with run().

    Construction opens no window. One stage may run at once, and each stage
    runs only once. Width/height are logical pixels; tick_rate defaults to 60.
    """

    __slots__ = (
        "_accumulator",
        "_actions",
        "_background",
        "_bubble_text_size",
        "_camera",
        "_clicks",
        "_draws",
        "_height",
        "_keyboard",
        "_keys",
        "_last_wall",
        "_members",
        "_message_handlers",
        "_messages",
        "_mouse",
        "_pause_reasons",
        "_pending",
        "_physics",
        "_starts",
        "_state",
        "_target",
        "_task",
        "_tick",
        "_tick_rate",
        "_updates",
        "_voices",
        "_volume",
        "_width",
    )

    def __init__(
        self,
        width: int = 480,
        height: int = 360,
        *,
        tick_rate: int = 60,
        background: Color = "black",
        bubble_text_size: int = 24,
        physics: bool = False,
    ) -> None:
        self._width = _integer(width, "width", minimum=1)
        self._bubble_text_size = _integer(bubble_text_size, "bubble_text_size", minimum=1)
        self._height = _integer(height, "height", minimum=1)
        self._tick_rate = _integer(tick_rate, "tick_rate", minimum=1)
        pygame.Color(background)
        self._background = background
        self._camera: Point = (0, 0)
        self._volume = 1.0
        self._members: list[_StageObject] = []
        self._updates: list[tuple[Actor | None, _Update]] = []
        self._keys: dict[Key, list[_Handler]] = {}
        self._actions: list[Action] = []
        self._starts: list[_Handler] = []
        self._clicks: dict[Actor | None, list[_Handler]] = {}
        self._messages: list[_Delivery] = []
        self._message_handlers: dict[Signal | Message[object], list[_Handler]] = {}
        self._draws: list[_Draw] = []
        self._keyboard = Keyboard()
        self._mouse = Mouse()
        self._pending: list[_InputEvent] = []
        self._state: Literal["new", "running", "closed"] = "new"
        self._pause_reasons: set[str] = set()
        self._tick = 0
        self._accumulator = 0.0
        self._last_wall: float | None = None
        self._voices: list[Voice] = []
        self._target: pygame.Surface | None = None
        self._task: asyncio.Task[None] | None = None
        if not isinstance(physics, bool):
            raise TypeError("physics must be bool")
        self._physics = Physics(self) if physics else None

    @property
    def physics(self) -> Physics:
        """This stage's optional world; enable with Stage(physics=True)."""
        from .errors import PhysicsError

        if self._physics is None:
            raise PhysicsError("Create the stage with physics=True")
        return self._physics

    @property
    def bubble_text_size(self) -> int:
        """Positive logical-pixel font size for every bubble; default 24.

        Changes apply on the next draw without restarting dialogue. Text stays
        upright and independent of actor scale. Too little viewport space hides
        the bubble rather than silently shrinking the requested size.
        """
        return self._bubble_text_size

    @bubble_text_size.setter
    def bubble_text_size(self, value: int) -> None:
        self._bubble_text_size = _integer(value, "bubble_text_size", minimum=1)

    @property
    def width(self) -> int:
        """Logical viewport width in pixels; resizing CSS does not change it."""
        return self._width

    @property
    def height(self) -> int:
        """Logical viewport height in pixels."""
        return self._height

    @property
    def tick_rate(self) -> int:
        """Fixed simulation updates per simulated second."""
        return self._tick_rate

    @property
    def time(self) -> float:
        """Simulated seconds since run started, excluding pause and dropped backlog."""
        return self._tick / self.tick_rate

    @property
    def running(self) -> bool:
        """True between run startup and stop, including while paused."""
        return self._state == "running"

    @property
    def paused(self) -> bool:
        """Whether user pause or automatic suspension currently freezes simulation."""
        return bool(self._pause_reasons)

    @property
    def keyboard(self) -> Keyboard:
        """Held-key input. Use is_down(Key.RIGHT) for continuous movement."""
        return self._keyboard

    @property
    def mouse(self) -> Mouse:
        """Mouse position in stage coordinates, and held mouse buttons."""
        return self._mouse

    @property
    def bounds(self) -> Bounds:
        """Viewport bounds in stage coordinates, independent of camera."""
        return Bounds(-self.width / 2, -self.height / 2, self.width / 2, self.height / 2)

    @property
    def world_bounds(self) -> Bounds:
        """The currently visible world rectangle, derived from viewport and camera."""
        x, y = self.camera
        bounds = self.bounds
        return Bounds(bounds.left + x, bounds.bottom + y, bounds.right + x, bounds.top + y)

    @property
    def camera(self) -> Point:
        """World position at the viewport center; (0, 0) shows the world origin."""
        return self._camera

    @camera.setter
    def camera(self, value: Point) -> None:
        self._camera = _point(value, "camera")

    @property
    def background(self) -> Color:
        """Color used to clear the viewport before drawing each frame."""
        return self._background

    @background.setter
    def background(self, value: Color) -> None:
        pygame.Color(value)
        self._background = value

    @property
    def volume(self) -> float:
        """Master sound volume, 0.0 silent through 1.0 full volume."""
        return self._volume

    @volume.setter
    def volume(self, value: float) -> None:
        self._volume = _volume(value)
        for voice in self._voices:
            if not voice.finished and voice._channel is not None:
                voice._channel.set_volume(self._volume)

    @property
    def objects(self) -> tuple[_StageObject, ...]:
        """A membership snapshot. Change membership with add/remove/clear."""
        return tuple(self._members)

    def add(self, obj: _StageObject) -> None:
        """Add an object once. Re-adding an existing member raises ValueError."""
        _open(self)
        if obj in self._members:
            raise ValueError("This object is already in the stage")
        if not isinstance(obj, (Sprite, Puppet, TileMap, TiledBackground)):
            raise TypeError("Stage objects are Sprite, Puppet, TileMap, or TiledBackground")
        if isinstance(obj, (Sprite, Puppet, TileMap)):
            if obj._stage is not None:
                raise StageError("An actor belongs to at most one stage")
            if self._physics is not None:
                from ._physics import _attach, _terrain

                if isinstance(obj, TileMap):
                    _terrain(self._physics, obj)
                else:
                    _attach(self._physics, obj)
            obj._stage = self
        self._members.append(obj)

    def remove(self, obj: _StageObject) -> None:
        """Detach an object; removing a nonmember raises ValueError."""
        if obj not in self._members:
            raise ValueError("This object is not in the stage")
        try:
            if isinstance(obj, (Sprite, Puppet)):
                _detach(self, obj)
            elif isinstance(obj, TileMap):
                if self._physics is not None:
                    from ._physics import _remove_terrain

                    _remove_terrain(self._physics, obj)
                obj._stage = None
        finally:
            if obj in self._members:
                self._members.remove(obj)

    def clear(self) -> None:
        """Detach all objects without changing their positions or visuals."""
        for obj in tuple(self._members):
            self.remove(obj)

    def on_update(self, callback: _Update) -> _Update:
        """Register a callback(dt: float) -> None. dt is fixed simulated seconds."""
        _open(self)
        _sync(callback, "update")
        self._updates.append((None, callback))
        return callback

    def _on_actor_update(self, actor: Actor, callback: _U) -> _U:
        _open(self)
        _actor(self, actor)
        from inspect import iscoroutinefunction

        if not callable(callback) or iscoroutinefunction(callback):
            raise TypeError("Actor update callbacks must be synchronous functions")
        self._updates.append((actor, callback))
        return callback

    @overload
    def on_start(self, actor: _P) -> _P: ...
    @overload
    def on_start(self, actor: _T, group: Group[_T]) -> None: ...
    def on_start(self, actor: object, group: object = None) -> object:
        """Register startup work before run; returning Action keeps the invocation alive."""
        if self._state != "new":
            raise StageError("Register startup handlers before run")
        if group is not None:
            self._starts.append(_binding(self, actor, group, WhenBusy.IGNORE))
            return None
        callback = cast(_Press, actor)
        self._starts.append(_Handler(lambda _: callback(), None, WhenBusy.IGNORE))
        return actor

    def _on_actor_start(self, actor: Actor, work: object) -> object:
        _actor(self, actor)
        if self._state != "new":
            raise StageError("Register startup handlers before run")
        if isinstance(work, Group):
            self._starts.append(_binding(self, actor, cast(object, work), WhenBusy.IGNORE))
            return None
        callback = cast(_Press, work)
        self._starts.append(_Handler(lambda _: callback(), actor, WhenBusy.IGNORE))
        return work

    @overload
    def on_key_down(
        self, key: Key, *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> Callable[[_P], _P]: ...
    @overload
    def on_key_down(
        self, key: Key, actor: _T, group: Group[_T], *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> None: ...
    def on_key_down(
        self,
        key: Key,
        actor: object = None,
        group: object = None,
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> object:
        """Bind a recipe or decorate a key callback; return Action for busy protection."""
        _open(self)
        if actor is not None:
            self._keys.setdefault(key, []).append(_binding(self, actor, group, when_busy))
            return None
        return self._key_decorator(key, None, when_busy)

    def _key_decorator(
        self, key: Key, actor: Actor | None, when_busy: WhenBusy
    ) -> Callable[[_P], _P]:
        def register(callback: _P) -> _P:
            _open(self)
            self._keys.setdefault(key, []).append(_Handler(lambda _: callback(), actor, when_busy))
            return callback

        return register

    @overload
    def on_click(self, actor: _C) -> _C: ...
    @overload
    def on_click(
        self, actor: _T, group: Group[_T], *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> None: ...
    def on_click(
        self, actor: object, group: object = None, *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> object:
        """Observe clicks anywhere; actor.on_click targets only the topmost hit actor."""
        _open(self)
        if group is not None:
            self._clicks.setdefault(None, []).append(_binding(self, actor, group, when_busy))
            return None
        self._clicks.setdefault(None, []).append(
            _click_handler(cast(_Click, actor), None, when_busy)
        )
        return actor

    def _on_actor_click(self, actor: Actor, work: object, when_busy: WhenBusy) -> object:
        _open(self)
        _actor(self, actor)
        if isinstance(work, Group):
            handler = _binding(self, actor, cast(object, work), when_busy)
            result: object = None
        else:
            if not callable(work):
                raise TypeError("Use a group or a callback(position, button)")
            handler = _click_handler(cast(_Click, work), actor, when_busy)
            result = work
        self._clicks.setdefault(actor, []).append(handler)
        return result

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
        actor: _T,
        group: Group[_T],
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None: ...
    def on_message(
        self,
        message: Signal | Message[_D],
        actor: object = None,
        group: object = None,
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> object:
        """Receive a token's typed payload; a directly bound group ignores the payload."""
        _open(self)
        token = cast("Signal | Message[object]", message)
        if actor is not None:
            self._message_handlers.setdefault(token, []).append(
                _binding(self, actor, group, when_busy)
            )
            return None
        return self._message_decorator(token, None, when_busy)

    def _message_decorator(
        self, message: Signal | Message[object], actor: Actor | None, when_busy: WhenBusy
    ) -> Callable[[object], object]:
        def register(callback: object) -> object:
            _open(self)

            def start(data: object) -> _Result:
                if isinstance(message, Signal):
                    return cast(_Press, callback)()
                return cast(Callable[[object], _Result], callback)(data)

            self._message_handlers.setdefault(message, []).append(_Handler(start, actor, when_busy))
            return callback

        return register

    def _enqueue(self, message: Signal | Message[object], data: object) -> _Delivery:
        if not self.running:
            raise StageError("Broadcast requires a running stage")
        if len(self._messages) >= 256:
            raise StageError(f"Message {message.name!r} exceeded the 256-delivery queue limit")
        delivery = _Delivery(message, data)
        self._messages.append(delivery)
        return delivery

    @overload
    def broadcast(self, message: Signal, *, after: Action | None = None) -> Action: ...
    @overload
    def broadcast(
        self, message: Message[_D], data: _D, *, after: Action | None = None
    ) -> Action: ...
    def broadcast(
        self, message: Signal | Message[_D], data: _D | None = None, *, after: Action | None = None
    ) -> Action:
        """Schedule FIFO delivery; complete after delivery, without joining receivers."""
        from ._commands import _broadcast

        return _admit(
            self,
            _broadcast(cast("Signal | Message[object]", message), data, False),
            None,
            after=after,
        )

    @overload
    def broadcast_and_wait(self, message: Signal, *, after: Action | None = None) -> Action: ...
    @overload
    def broadcast_and_wait(
        self, message: Message[_D], data: _D, *, after: Action | None = None
    ) -> Action: ...
    def broadcast_and_wait(
        self, message: Signal | Message[_D], data: _D | None = None, *, after: Action | None = None
    ) -> Action:
        """Schedule delivery and wait for accepted receiver invocations; skipped busy receivers are excluded."""
        from ._commands import _broadcast

        return _admit(
            self,
            _broadcast(cast("Signal | Message[object]", message), data, True),
            None,
            after=after,
        )

    def wait(self, seconds: float, *, after: Action | None = None) -> Action:
        """Schedule a simulation-time wait; zero yields until the next tick."""
        from ._operations import _wait
        from .geometry import _number

        seconds = _number(seconds, "seconds", minimum=0)
        return _admit(self, _wait(self, seconds), None, after=after)

    def call(self, function: Callable[[], None | Action], *, after: Action | None = None) -> Action:
        """Run a synchronous function when reached and wait for its returned Action."""
        from ._commands import _call

        if not callable(function):
            raise TypeError("call expects a function, not its result")
        return _admit(self, _call(function), None, after=after)

    def join(self, first: Action, *rest: Action, after: Action | None = None) -> Action:
        """Wait for independent actions; canceling this join does not cancel them."""
        from ._commands import _join

        actions = (first, *rest)
        if any(action._stage is not self for action in actions):
            raise StageError("Join actions from the same stage")
        return _admit(self, _join(actions), None, after=after)

    def on_draw(self, callback: _Draw) -> _Draw:
        """Register a Canvas callback drawn above the scene, also while paused."""
        _open(self)
        _sync(callback, "draw")
        self._draws.append(callback)
        return callback

    def to_screen(self, point: Point, *, world: bool = True) -> Point:
        """Convert centered coordinates to top-left screen pixels; world applies camera."""
        x, y = _point(point)
        cx, cy = self.camera if world else (0, 0)
        return self.width / 2 + x - cx, self.height / 2 - y + cy

    def from_screen(self, point: Point, *, world: bool = True) -> Point:
        """Convert top-left screen pixels to centered world or stage coordinates."""
        x, y = _point(point)
        cx, cy = self.camera if world else (0, 0)
        return x - self.width / 2 + cx, self.height / 2 - y + cy

    def pause(self) -> None:
        """Freeze simulation/audio. Input and drawing callbacks continue."""
        if not self.running:
            raise StageError("Pause requires a running stage")
        self._set_pause("user", True)

    def resume(self) -> None:
        """Remove user pause; automatic suspension may still keep the stage paused."""
        if not self.running:
            raise StageError("Resume requires a running stage")
        self._set_pause("user", False)

    def _set_pause(self, reason: str, paused: bool) -> None:
        before = self.paused
        if paused:
            self._pause_reasons.add(reason)
        else:
            self._pause_reasons.discard(reason)
        if before != self.paused:
            self._accumulator = 0
            self._last_wall = None
            if pygame.mixer.get_init() is not None:
                if self.paused:
                    pygame.mixer.pause()
                else:
                    pygame.mixer.unpause()

    def play(self, sound: Sound, *, volume: float = 1, loop: bool = False) -> Voice:
        """Play an OGG occurrence; raises AudioError if no device/channel is available."""
        if not self.running:
            raise StageError("Play sound after stage.run starts, inside a callback")
        self._voices[:] = [voice for voice in self._voices if not voice.finished]
        voice = _play(sound, _volume(volume), loop)
        if voice._channel is not None:
            voice._channel.set_volume(self.volume)
            if self.paused:
                voice._channel.pause()
        self._voices.append(voice)
        return voice

    def stop_sounds(self) -> None:
        """Stop and invalidate every current voice belonging to this stage."""
        for voice in self._voices:
            voice.stop()
        self._voices.clear()

    def stop(self) -> None:
        """End this stage. Calling stop again is harmless; run cannot restart it."""
        self._state = "closed"

    def run(self) -> None:
        """Start once; place this last in the entry script. Browser launch schedules a task.

        Desktop execution returns after closure. Statements after run are not
        portable. Raises StageError for reuse or conflicting display resources.
        """
        from ._runtime import start

        start(self)


def _open(stage: Stage) -> None:
    if stage._state == "closed":
        raise StageError("This stage is closed")


def _actor(stage: Stage, value: object) -> Actor:
    if not isinstance(value, (Sprite, Puppet)) or value._stage is not stage:
        raise StageError("Add the actor to this stage before binding events")
    return value


def _binding(stage: Stage, actor: object, group: object, when_busy: WhenBusy) -> _Handler:
    target = _actor(stage, actor)
    if not isinstance(group, Group) or cast(Group[Actor], group)._actor is not target:
        raise TypeError("Bind a group belonging to this exact actor")
    recipe = cast(Group[Actor], group)

    def start(_: object) -> Action:
        from ._commands import _schedule
        from .groups import _snapshot

        return _schedule(target, _snapshot(recipe, target))

    return _Handler(start, target, when_busy)


def _click_handler(callback: _Click, actor: Actor | None, when_busy: WhenBusy) -> _Handler:
    def start(data: object) -> _Result:
        position, button = cast(tuple[Point, MouseButton], data)
        return callback(position, button)

    return _Handler(start, actor, when_busy)


def _attached(actor: Actor) -> Stage:
    if actor._stage is None:
        raise StageError("Add the actor to a stage before registering events")
    _open(actor._stage)
    return actor._stage


def _sync(callback: object, kind: str) -> None:
    from inspect import iscoroutinefunction

    if not callable(callback) or iscoroutinefunction(callback):
        raise TypeError(f"{kind} callbacks must be synchronous functions returning None")


def _check_callback_result(result: object, kind: str) -> None:
    if result is not None:
        from collections.abc import Coroutine

        if isinstance(result, Coroutine):
            result.close()
        raise TypeError(f"{kind} callbacks must return None, not an Action or coroutine")
