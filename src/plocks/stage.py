"""Explicit scene membership, event registration, and fixed-step execution."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Literal, TypeVar, cast, overload

import pygame

from ._operations import _context, _Delivery, _Join, _suspend
from ._scripts import WhenBusy, _detach, _Handler, _Run
from .audio import Sound, Voice, _play, _volume
from .blocks import Actor, Block
from .canvas import Canvas
from .errors import StageError
from .geometry import Bounds, Color, Point, _integer, _point
from .input import Key, Keyboard, Mouse, MouseButton
from .messages import Message, Signal
from .puppets import Puppet
from .sprites import Sprite
from .tiling import TiledBackground, TileMap

type _Update = Callable[[float], None]
type _Press = Callable[[], None | Coroutine[object, object, None]]
_P = TypeVar("_P", bound=_Press)
type _Result = None | Coroutine[object, object, None]
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
        "_runs",
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
        self._updates: list[_Update] = []
        self._keys: dict[Key, list[_Handler]] = {}
        self._runs: list[_Run] = []
        self._starts: list[_Handler] = []
        self._clicks: list[_Handler] = []
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
        if isinstance(obj, (Sprite, Puppet)):
            if obj._stage is not None:
                raise StageError("An actor belongs to at most one stage")
            obj._stage = self
        self._members.append(obj)

    def remove(self, obj: _StageObject) -> None:
        """Detach an object; removing a nonmember raises ValueError."""
        if obj not in self._members:
            raise ValueError("This object is not in the stage")
        try:
            if isinstance(obj, (Sprite, Puppet)):
                _detach(self, obj)
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
        self._updates.append(callback)
        return callback

    @overload
    def on_start(self, actor: _P) -> _P: ...
    @overload
    def on_start(self, actor: _T, block: Block[_T]) -> None: ...
    def on_start(self, actor: object, block: object = None) -> object:
        """Bind a startup block or decorate a sync/async function; register before run."""
        if self._state != "new":
            raise StageError("Register startup handlers before run")
        if block is not None:
            self._starts.append(_binding(self, actor, block, WhenBusy.IGNORE))
            return None
        callback = cast(_Press, actor)
        self._starts.append(_Handler(lambda _: callback(), None, None, WhenBusy.IGNORE))
        return actor

    @overload
    def on_key_down(
        self, key: Key, *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> Callable[[_P], _P]: ...
    @overload
    def on_key_down(
        self, key: Key, actor: _T, block: Block[_T], *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> None: ...
    def on_key_down(
        self,
        key: Key,
        actor: object = None,
        block: object = None,
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> object:
        """Bind a block or decorate a sync/async handler. Busy triggers default to ignore."""
        _open(self)
        if actor is not None:
            self._keys.setdefault(key, []).append(_binding(self, actor, block, when_busy))
            return None

        def register(callback: _P) -> _P:
            _open(self)
            self._keys.setdefault(key, []).append(
                _Handler(lambda _: callback(), None, None, when_busy)
            )
            return callback

        return register

    @overload
    def on_click(self, actor: _C) -> _C: ...
    @overload
    def on_click(
        self, actor: _T, block: Block[_T], *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> None: ...
    def on_click(
        self, actor: object, block: object = None, *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> object:
        """Bind a block, or decorate a typed callback(position, button); async is supported."""
        _open(self)
        if block is not None:
            self._clicks.append(_binding(self, actor, block, when_busy))
            return None
        callback = cast(_Click, actor)

        def start(data: object) -> _Result:
            position, button = cast(tuple[Point, MouseButton], data)
            return callback(position, button)

        self._clicks.append(_Handler(start, None, None, when_busy))
        return actor

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
        self, message: Signal, actor: _T, block: Block[_T], *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> None: ...
    @overload
    def on_message(
        self,
        message: Message[_D],
        actor: _T,
        block: Callable[[_D], Block[_T]],
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None: ...
    def on_message(
        self,
        message: Signal | Message[_D],
        actor: object = None,
        block: object = None,
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> object:
        """Receive a signal, typed payload, or payload-to-block factory; matching token identity matters."""
        _open(self)
        token = cast("Signal | Message[object]", message)
        if actor is not None:
            if isinstance(message, Signal):
                handler = _binding(self, actor, block, when_busy)
            else:
                target = _actor(self, actor)
                factory = cast(Callable[[object], Block[Actor]], block)

                async def receive(data: object) -> None:
                    recipe = factory(data)
                    if not isinstance(recipe, Block):
                        raise TypeError("A message factory must return a Block")
                    await recipe.run(target)

                handler = _Handler(receive, target, None, when_busy)
            self._message_handlers.setdefault(token, []).append(handler)
            return None

        def register(callback: object) -> object:
            _open(self)

            def start(data: object) -> _Result:
                if isinstance(message, Signal):
                    return cast(_Press, callback)()
                return cast(Callable[[object], _Result], callback)(data)

            self._message_handlers.setdefault(token, []).append(
                _Handler(start, None, None, when_busy)
            )
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
    def broadcast(self, message: Signal) -> None: ...
    @overload
    def broadcast(self, message: Message[_D], data: _D) -> None: ...
    def broadcast(self, message: Signal | Message[_D], data: _D | None = None) -> None:
        """Queue stage-local delivery; no receiver runs inline. Payloads are shared by reference."""
        self._enqueue(cast("Signal | Message[object]", message), data)

    @overload
    async def broadcast_and_wait(self, message: Signal) -> None: ...
    @overload
    async def broadcast_and_wait(self, message: Message[_D], data: _D) -> None: ...
    async def broadcast_and_wait(
        self, message: Signal | Message[_D], data: _D | None = None
    ) -> None:
        """Advanced: deliver and await accepted receiver invocations, excluding skipped busy handlers."""
        stage, _, _, _ = await _context()
        if stage is not self:
            raise StageError("Use the executing stage for message waits")
        await _suspend(_Join(self._enqueue(cast("Signal | Message[object]", message), data)))

    async def wait(self, seconds: float) -> None:
        """Advanced: await simulated seconds; zero yields until the next tick."""
        from ._operations import _wait

        await _wait(self, seconds)

    def on_draw(self, callback: _Draw) -> _Draw:
        """Register a Canvas callback drawn above the scene, also while paused."""
        _open(self)
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


def _binding(stage: Stage, actor: object, block: object, when_busy: WhenBusy) -> _Handler:
    target = _actor(stage, actor)
    if not isinstance(block, Block):
        raise TypeError("Event bindings require a Block, not the result of actor.act")
    recipe = cast(Block[Actor], block)
    return _Handler(lambda _: recipe.run(target), target, recipe, when_busy)
