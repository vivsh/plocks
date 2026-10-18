"""Explicit scene membership, event registration, and fixed-step execution."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Generic, Literal, Self, TypeVar, cast, overload

import pygame

from ._commands import Actor, _Command
from ._operations import _Delivery
from ._scripts import WhenBusy, _admit, _detach, _Handler, _InputBinding
from .actions import Action
from .audio import Sound, Voice, _play, _volume
from .callbacks import ActorUpdateCallback, UpdateCallback
from .canvas import Canvas
from .errors import StageError
from .events import Click, Event, GamepadPress
from .gamepads import Gamepad, GamepadButton, GamepadLayout, _new_gamepad
from .geometry import Bounds, Color, Point, _integer, _point
from .input import Key, Keyboard, Mouse, MouseButton
from .messages import Message
from .physics import Physics
from .puppets import Puppet
from .scripts import Script, _message_arguments, _snapshot
from .sprites import Sprite
from .state import _new_state, _State_co
from .tiling import TiledBackground, TileMap

type _Result = None | Action
_D = TypeVar("_D")
_R = TypeVar("_R", bound=_Result)
type _Draw = Callable[[Canvas], None]
type _InputEvent = Key | tuple[Point, MouseButton] | GamepadPress
type _StageObject = Sprite | Puppet | TileMap | TiledBackground


class Stage(Generic[_State_co]):  # noqa: UP046 -- default state type supports Python 3.12
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
        "_game_state",
        "_gamepad_handlers",
        "_gamepads",
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

    @overload
    def __init__(
        self: Stage[None],
        width: int = 480,
        height: int = 360,
        *,
        tick_rate: int = 60,
        background: Color = "black",
        bubble_text_size: int = 24,
        physics: bool = False,
        gamepad_count: int = 4,
        gamepad_layout: GamepadLayout = GamepadLayout.XBOX,
        state: None = None,
    ) -> None: ...
    @overload
    def __init__(
        self,
        width: int = 480,
        height: int = 360,
        *,
        tick_rate: int = 60,
        background: Color = "black",
        bubble_text_size: int = 24,
        physics: bool = False,
        gamepad_count: int = 4,
        gamepad_layout: GamepadLayout = GamepadLayout.XBOX,
        state: type[_State_co],
    ) -> None: ...
    def __init__(
        self,
        width: int = 480,
        height: int = 360,
        *,
        tick_rate: int = 60,
        background: Color = "black",
        bubble_text_size: int = 24,
        physics: bool = False,
        gamepad_count: int = 4,
        gamepad_layout: GamepadLayout = GamepadLayout.XBOX,
        state: type[object] | None = None,
    ) -> None:
        self._game_state: _State_co = cast(_State_co, _new_state(state))
        self._width = _integer(width, "width", minimum=1)
        self._bubble_text_size = _integer(bubble_text_size, "bubble_text_size", minimum=1)
        self._height = _integer(height, "height", minimum=1)
        self._tick_rate = _integer(tick_rate, "tick_rate", minimum=1)
        pygame.Color(background)
        self._background = background
        self._camera: Point = (0, 0)
        self._volume = 1.0
        self._members: list[_StageObject] = []
        self._updates: list[tuple[Actor | None, UpdateCallback | ActorUpdateCallback[Actor]]] = []
        self._keys: dict[Key, list[_InputBinding]] = {}
        self._gamepad_handlers: dict[tuple[Gamepad, GamepadButton], list[_InputBinding]] = {}
        self._actions: list[Action] = []
        self._starts: list[_Handler] = []
        self._clicks: dict[Actor | None, list[_Handler]] = {}
        self._messages: list[_Delivery] = []
        self._message_handlers: dict[Message[object], list[_Handler]] = {}
        self._draws: list[_Draw] = []
        count = _integer(gamepad_count, "gamepad_count", minimum=1)
        if count > 16:
            raise ValueError("gamepad_count must be at most 16")
        if not isinstance(gamepad_layout, GamepadLayout):
            raise TypeError("Use a GamepadLayout")
        self._gamepads = tuple(_new_gamepad(self, gamepad_layout, index) for index in range(count))
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
    def gamepads(self) -> tuple[Gamepad, ...]:
        """Stable player slots (four by default); keyboard mapping needs no hardware."""
        return self._gamepads

    @property
    def state(self) -> _State_co:
        """This owner's dataclass instance, or None when state was not supplied.

        The association is read-only; its fields follow ordinary Python behavior.
        Each owner constructs its own instance. Values survive removal and closure.
        """
        return self._game_state

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
                from ._gamepads import _input_bindings

                for binding in _input_bindings(self):
                    if binding.handler.actor is obj:
                        binding.next_repeat = None
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

    def on_update(
        self, callback: Callable[[Event[Self, float]], None]
    ) -> Callable[[Event[Self, float]], None]:
        """Register a callback(event) -> None; event.data is fixed simulated seconds."""
        _open(self)
        _sync(callback, "update")
        self._updates.append((None, cast(UpdateCallback, callback)))
        return callback

    def _on_actor_update(self, actor: Actor, callback: object) -> object:
        _open(self)
        _actor(self, actor)
        _sync(callback, "actor update")
        self._updates.append((actor, cast(ActorUpdateCallback[Actor], callback)))
        return callback

    @overload
    def on_start(
        self, work: Callable[[Event[Self, None]], _R]
    ) -> Callable[[Event[Self, None]], _R]: ...
    @overload
    def on_start(self, work: Sprite, script: Script[Actor] | Script[Sprite]) -> None: ...
    @overload
    def on_start(self, work: Puppet, script: Script[Actor] | Script[Puppet]) -> None: ...
    def on_start(self, work: object, script: object = None) -> object:
        """Register startup callback(event) or actor/Script before run."""
        if self._state != "new":
            raise StageError("Register startup handlers before run")
        self._starts.append(
            _binding(self, work, script, WhenBusy.IGNORE)
            if script is not None
            else _callback_handler(work, None, WhenBusy.IGNORE)
        )
        return None if script is not None else work

    def _on_actor_start(self, actor: Actor, work: object) -> object:
        _actor(self, actor)
        if self._state != "new":
            raise StageError("Register startup handlers before run")
        self._starts.append(_work_handler(self, actor, work, WhenBusy.IGNORE))
        return None if isinstance(work, Script) else work

    @overload
    def on_key_down(
        self, key: Key, *, repeat: float | None = None, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> Callable[[Callable[[Event[Self, Key]], _R]], Callable[[Event[Self, Key]], _R]]: ...
    @overload
    def on_key_down(
        self,
        key: Key,
        actor: Sprite,
        script: Script[Actor] | Script[Sprite],
        *,
        repeat: float | None = None,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None: ...
    @overload
    def on_key_down(
        self,
        key: Key,
        actor: Puppet,
        script: Script[Actor] | Script[Puppet],
        *,
        repeat: float | None = None,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None: ...
    def on_key_down(
        self,
        key: Key,
        actor: object = None,
        script: object = None,
        *,
        repeat: float | None = None,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> object:
        """Bind a Script or callback(event) to a fresh key transition."""
        _open(self)
        repeat = _repeat_interval(repeat)
        if not isinstance(key, Key):
            raise TypeError("Use a Key enum value")
        if actor is not None:
            handler = _binding(self, actor, script, when_busy)
            self._keys.setdefault(key, []).append(_InputBinding(handler, repeat))
            return None
        return self._key_decorator(key, None, when_busy, repeat)

    def _key_decorator(
        self, key: Key, actor: Actor | None, when_busy: WhenBusy, repeat: float | None = None
    ) -> Callable[[object], object]:
        repeat = _repeat_interval(repeat)

        def register(callback: object) -> object:
            _open(self)
            if not isinstance(key, Key):
                raise TypeError("Use a Key enum value")
            handler = _callback_handler(callback, actor, when_busy)
            self._keys.setdefault(key, []).append(_InputBinding(handler, repeat))
            return callback

        return register

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
        actor: Sprite,
        script: Script[Actor] | Script[Sprite],
        *,
        gamepad: Gamepad | None = None,
        repeat: float | None = None,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None: ...
    @overload
    def on_gamepad_button_down(
        self,
        button: GamepadButton,
        actor: Puppet,
        script: Script[Actor] | Script[Puppet],
        *,
        gamepad: Gamepad | None = None,
        repeat: float | None = None,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None: ...
    def on_gamepad_button_down(
        self,
        button: GamepadButton,
        actor: object = None,
        script: object = None,
        *,
        gamepad: Gamepad | None = None,
        repeat: float | None = None,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> object:
        """Bind a script or callback(Event) to a logical gamepad press.

        Omit gamepad to listen to all player slots. repeat is an optional positive
        simulation-second interval; otherwise only the initial press fires.
        Event.data contains gamepad and button; Event.source is this Stage.
        """
        _open(self)
        repeat = _repeat_interval(repeat)
        _gamepad_selection(self, button, gamepad)
        if actor is not None:
            handler = _binding(self, actor, script, when_busy)
            self._register_gamepad(button, gamepad, handler, repeat)
            return None
        return self._gamepad_decorator(button, None, gamepad, repeat, when_busy)

    def _register_gamepad(
        self,
        button: GamepadButton,
        gamepad: Gamepad | None,
        handler: _Handler,
        repeat: float | None,
    ) -> None:
        for slot in self.gamepads if gamepad is None else (gamepad,):
            self._gamepad_handlers.setdefault((slot, button), []).append(
                _InputBinding(handler, repeat)
            )

    def _gamepad_decorator(
        self,
        button: GamepadButton,
        actor: Actor | None,
        gamepad: Gamepad | None,
        repeat: float | None,
        when_busy: WhenBusy,
    ) -> Callable[[object], object]:
        def register(callback: object) -> object:
            _open(self)
            _gamepad_selection(self, button, gamepad)
            handler = _callback_handler(callback, actor, when_busy)
            self._register_gamepad(button, gamepad, handler, repeat)
            return callback

        return register

    def on_click(
        self, callback: Callable[[Event[Self, Click]], _R]
    ) -> Callable[[Event[Self, Click]], _R]:
        """Observe every pointer-down with callback(event); event.data is (point,button)."""
        _open(self)
        handler = _callback_handler(callback, None, WhenBusy.IGNORE)
        self._clicks.setdefault(None, []).append(handler)
        return callback

    def _on_actor_click(self, actor: Actor, work: object, when_busy: WhenBusy) -> object:
        _open(self)
        _actor(self, actor)
        handler = _work_handler(self, actor, work, when_busy)
        self._clicks.setdefault(actor, []).append(handler)
        return None if isinstance(work, Script) else work

    @overload
    def on_broadcast(
        self, message: Message[_D], *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> Callable[[Callable[[Event[Self, _D]], _R]], Callable[[Event[Self, _D]], _R]]: ...
    @overload
    def on_broadcast(
        self,
        message: Message[_D],
        actor: Sprite,
        script: Script[Actor] | Script[Sprite],
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None: ...
    @overload
    def on_broadcast(
        self,
        message: Message[_D],
        actor: Puppet,
        script: Script[Actor] | Script[Puppet],
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None: ...
    def on_broadcast(
        self,
        message: Message[_D],
        actor: object = None,
        script: object = None,
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> object:
        """Receive Event[Stage, Payload], or bind a compatible actor/Script."""
        _open(self)
        _message_arguments(message, None, False)
        token = cast(Message[object], message)
        if actor is not None:
            handler = _binding(self, actor, script, when_busy)
            self._message_handlers.setdefault(token, []).append(handler)
            return None
        return self._message_decorator(token, None, when_busy)

    def _message_decorator(
        self, message: Message[object], actor: Actor | None, when_busy: WhenBusy
    ) -> Callable[[object], object]:
        def register(callback: object) -> object:
            _open(self)
            _message_arguments(message, None, False)
            handler = _callback_handler(callback, actor, when_busy)
            self._message_handlers.setdefault(message, []).append(handler)
            return callback

        return register

    def _enqueue(
        self,
        message: Message[object],
        source: Stage | Actor,
        data: object,
        destination: Actor | None,
    ) -> _Delivery:
        if not self.running:
            raise StageError("Sending requires a running stage")
        if destination is not None and destination._stage is not self:
            raise StageError("Message destination must belong to this stage")
        if len(self._messages) >= 256:
            raise StageError(f"Message {message.name!r} exceeded the 256-delivery queue limit")
        delivery = _Delivery(message, source, data, destination)
        self._messages.append(delivery)
        return delivery

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
        """Schedule FIFO delivery from Stage; wait joins accepted receivers.

        Default is stage-wide. An explicit destination receives exclusively.
        Payload is captured by reference; effects start in the next eligible phase.
        """
        from ._commands import _send

        _message_arguments(message, to, wait)
        return _admit(
            self, _send(cast(Message[object], message), data, self, to, wait), None, after=after
        )

    def wait(self, seconds: float, *, after: Action | None = None) -> Action:
        """Schedule a simulation-time wait; zero yields until the next tick."""
        from ._operations import _wait
        from .geometry import _number

        seconds = _number(seconds, "seconds", minimum=0)
        return _admit(self, _wait(self, seconds), None, after=after)

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
        """End this stage; an IPython prompt call also releases its window immediately.

        Calling stop again is harmless. A closed stage cannot restart; make a new
        Stage instead. A call inside a game callback cleans up after that callback.
        """
        self._state = "closed"
        if self._task is not None:
            from ._ipython import _stop

            _stop(self)

    def run(self, *, interactive: bool = False) -> None:
        """Open a desktop window once; optionally keep a terminal IPython prompt usable.

        With interactive=False (default), return after the window closes and
        resources are released. With interactive=True, return to terminal IPython
        immediately; edit actors at the prompt and call stop() to close the game.
        Switching to the terminal clears held input without suspending simulation.
        Minimized/hidden windows and pause() still suspend simulation and audio.

        IPython 9.x is optional and must use its full terminal prompt. Notebooks and
        plain Python shells do not support interactive=True. Long Python commands
        block the shared main thread. Raises StageError for unsupported contexts,
        reuse, conflicting event loops, or already-active native resources.
        """
        if not isinstance(interactive, bool):
            raise TypeError("interactive must be bool")
        if interactive:
            from ._ipython import _start

            _start(self)
        else:
            from ._runtime import start

            start(self)


def _open(stage: Stage) -> None:
    if stage._state == "closed":
        raise StageError("This stage is closed")


def _actor(stage: Stage, value: object) -> Actor:
    if not isinstance(value, (Sprite, Puppet)) or value._stage is not stage:
        raise StageError("Add the actor to this stage before binding events")
    return cast(Actor, value)


def _binding(stage: Stage, actor: object, script: object, when_busy: WhenBusy) -> _Handler:
    target = _actor(stage, actor)
    if not isinstance(when_busy, WhenBusy):
        raise TypeError("Use WhenBusy.IGNORE or RESTART")
    if not isinstance(script, Script):
        raise TypeError("Bind a Script, not an actor-bound group")
    recipe = cast(Script[Actor], script)
    _snapshot(recipe, target)

    def start(_: Event[Stage | Actor, object]) -> _Command[Actor]:
        return _snapshot(recipe, target)

    return _Handler(start, target, when_busy)


def _work_handler(stage: Stage, actor: Actor, work: object, when_busy: WhenBusy) -> _Handler:
    return (
        _binding(stage, actor, cast(object, work), when_busy)
        if isinstance(work, Script)
        else _callback_handler(work, actor, when_busy)
    )


def _callback_handler(callback: object, actor: Actor | None, when_busy: WhenBusy) -> _Handler:
    _sync(callback, "event")
    if not isinstance(when_busy, WhenBusy):
        raise TypeError("Use WhenBusy.IGNORE or RESTART")

    def start(event: Event[Stage | Actor, object]) -> None | Action | _Command[Actor]:
        result = cast(Callable[[object], object], callback)(event)
        if result is None or isinstance(result, Action):
            return result
        if isinstance(result, Script):
            if actor is None:
                raise TypeError(
                    "A Stage callback cannot return an unbound Script; return actor.act(script)"
                )
            return _snapshot(cast(Script[Actor], result), actor)
        _reject_result(
            result,
            "Event callbacks must return None, a same-stage Action, or an actor-compatible Script",
        )
        return None

    return _Handler(start, actor, when_busy)


def _attached(actor: Actor) -> Stage:
    if actor._stage is None:
        raise StageError("Add the actor to a stage before registering events")
    _open(actor._stage)
    return actor._stage


def _sync(callback: object, kind: str) -> None:
    from inspect import isasyncgenfunction, iscoroutinefunction, isgeneratorfunction, unwrap

    if not callable(callback):
        raise TypeError(f"{kind} callbacks must be synchronous functions")
    function = unwrap(callback)
    for candidate in (function, unwrap(function.__call__)):
        if (
            iscoroutinefunction(candidate)
            or isasyncgenfunction(candidate)
            or isgeneratorfunction(candidate)
        ):
            raise TypeError(f"{kind} callbacks must be synchronous functions")


def _reject_result(result: object, message: str) -> None:
    from collections.abc import Coroutine, Generator

    error = TypeError(message)
    if isinstance(result, (Coroutine, Generator)):
        try:
            result.close()
        except BaseException as cleanup:  # noqa: BLE001 -- retain the contract failure when result cleanup fails
            error.add_note(f"Rejected callback result cleanup also failed: {cleanup!r}")
    raise error


def _check_callback_result(result: object, kind: str) -> None:
    if result is not None:
        _reject_result(
            result, f"{kind} callbacks must return None, not an Action, Script or coroutine"
        )


def _repeat_interval(value: float | None) -> float | None:
    from .geometry import _positive

    return None if value is None else _positive(value, "repeat")


def _gamepad_selection(stage: Stage, button: GamepadButton, gamepad: Gamepad | None) -> None:
    if not isinstance(button, GamepadButton):
        raise TypeError("Use a GamepadButton")
    if gamepad is not None and (not isinstance(gamepad, Gamepad) or gamepad._stage is not stage):
        raise StageError("Use a gamepad slot belonging to this stage")
