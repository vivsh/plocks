"""A shared yielding driver; all retained execution state belongs to Stage."""

from __future__ import annotations

import asyncio
import atexit
import sys
import time
from importlib.resources import files
from typing import TYPE_CHECKING, cast

import pygame

from . import _gamepads
from ._cloning import _CloneStart, _start_clone
from ._render import frame
from ._scripts import _cancel, _deliver, _sample, _step, _trigger
from .callbacks import ActorUpdateCallback, UpdateCallback
from .errors import StageError
from .events import Event, GamepadPress, RemoteChange
from .geometry import Point
from .input import Key, MouseButton
from .multiplayer import Multiplayer

if TYPE_CHECKING:
    from ._commands import Actor
    from .stage import Stage


def _check_start(stage: Stage) -> None:
    """Reject stage reuse and conflicting display/audio owners before acquisition."""
    if stage._state != "new":
        raise StageError("A stage can run once; create a new Stage to start again")
    if pygame.display.get_surface() is not None:
        raise StageError("Another Pygame display is already active")
    if pygame.mixer.get_init() is not None:
        raise StageError("Another Pygame audio session is already active")


def _acquire(stage: Stage, multiplayer: Multiplayer | None = None) -> None:
    """Acquire the same desktop resources for blocking and interactive execution."""
    _gamepads._check_devices()
    try:
        if multiplayer is not None:
            try:
                from ._network import _host
            except ImportError as error:
                from .errors import NetworkError

                raise NetworkError(
                    "Multiplayer needs Plocks installed with its [network] extra"
                ) from error
            stage._network = _host(stage, multiplayer)
        pygame.display.init()
        with files("plocks").joinpath("assets/icon.png").open("rb") as source:
            pygame.display.set_icon(pygame.image.load(source, "icon.png"))
        pygame.display.set_caption("Plocks")
        stage._target = pygame.display.set_mode((stage.width, stage.height))
        pygame.event.clear()
        _gamepads._open_devices(stage)
        stage._state = "running"
    except BaseException:
        pygame.display.quit()
        close(stage)
        raise


def start(stage: Stage, multiplayer: Multiplayer | None = None) -> None:
    """Acquire one desktop display and block until closure, releasing owned resources."""
    _check_start(stage)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise StageError("Desktop run() requires a script outside an existing asyncio loop")
    _acquire(stage, multiplayer)
    try:
        asyncio.run(drive(stage))
    except BaseException:
        close(stage)
        raise


def _clear_input(stage: Stage) -> None:
    stage._held_keys.clear()
    stage.mouse._down.clear()
    stage._pending[:] = [
        event for event in stage._pending if stage.running and isinstance(event, _CloneStart)
    ]
    _gamepads._clear_repeats(stage)
    for slot in stage.gamepads:
        _gamepads._clear_sample(slot)


def poll(stage: Stage) -> None:
    """Translate desktop window, controller, keyboard and mouse events once."""
    was_suspended = bool(stage._pause_reasons - {"user"})
    refresh = False
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            stage.stop()
        elif event.type in (
            pygame.WINDOWFOCUSLOST,
            pygame.WINDOWHIDDEN,
            pygame.WINDOWMINIMIZED,
        ):
            _clear_input(stage)
            was_suspended = True
            reason = {
                pygame.WINDOWFOCUSLOST: "focus",
                pygame.WINDOWHIDDEN: "hidden",
                pygame.WINDOWMINIMIZED: "minimized",
            }[event.type]
            if reason != "focus" or stage._task is None:
                stage._set_pause(reason, True)
        elif event.type in (
            pygame.WINDOWFOCUSGAINED,
            pygame.WINDOWSHOWN,
            pygame.WINDOWRESTORED,
        ):
            reason = {
                pygame.WINDOWFOCUSGAINED: "focus",
                pygame.WINDOWSHOWN: "hidden",
                pygame.WINDOWRESTORED: "minimized",
            }[event.type]
            stage._set_pause(reason, False)
        elif event.type in (pygame.CONTROLLERDEVICEADDED, pygame.CONTROLLERDEVICEREMOVED):
            refresh = True
        elif event.type in (
            pygame.CONTROLLERBUTTONDOWN,
            pygame.CONTROLLERBUTTONUP,
        ):
            if not was_suspended and not (stage._pause_reasons - {"user"}):
                _gamepads._native_button_event(stage, event)
        elif event.type in (pygame.KEYDOWN, pygame.KEYUP):
            _key(stage, event)
        elif event.type == pygame.MOUSEMOTION:
            stage.mouse._position = stage.from_screen(event.pos, world=False)
        elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            _mouse(stage, event)
    suspended = bool(stage._pause_reasons - {"user"})
    if suspended:
        _clear_input(stage)
    else:
        _gamepads._poll_devices(stage, baseline=was_suspended, refresh=refresh)
        if was_suspended:
            _gamepads._resume_repeats(stage)


def _key(stage: Stage, event: pygame.event.Event) -> None:
    try:
        key = Key(pygame.key.name(event.key))
    except ValueError:
        return
    before = tuple(_gamepads._held(slot) for slot in stage.gamepads)
    if event.type == pygame.KEYDOWN:
        stage._held_keys.add(key)
    else:
        stage._held_keys.discard(key)
    for slot, held in zip(stage.gamepads, before):
        _gamepads._transitions(slot, held)


def _mouse(stage: Stage, event: pygame.event.Event) -> None:
    try:
        button = MouseButton(event.button)
    except ValueError:
        return
    position = stage.from_screen(event.pos, world=False)
    stage.mouse._position = position
    if event.type == pygame.MOUSEBUTTONDOWN:
        stage.mouse._down.add(button)
        stage._pending.append((position, button))
    else:
        stage.mouse._down.discard(button)


def dispatch(stage: Stage, *, simulation: bool = True) -> None:
    """Consume edge events once; clone starts wait for an eligible simulation phase."""
    pending = tuple(stage._pending)
    stage._pending.clear()
    clone_ready = simulation and not stage.paused
    for event in pending:
        if not stage.running:
            break
        if isinstance(event, RemoteChange):
            from .stage import _check_callback_result

            for callback in tuple(stage._remote_handlers):
                _check_callback_result(callback(Event(stage, stage, event)), "remote change")
            continue
        if isinstance(event, _CloneStart):
            clone_ready = clone_ready and not stage.paused
            if not clone_ready:
                stage._pending.append(event)
            else:
                _start_clone(stage, event)
            continue
        if isinstance(event, GamepadPress):
            bindings = tuple(stage._gamepad_handlers.get((event.gamepad, event.button), ()))
            for binding in bindings:
                if stage.running:
                    held = event.gamepad.is_down(event.button)
                    _gamepads._arm(stage, binding, held)
                    _trigger(stage, binding.handler, event)
        if isinstance(event, tuple):
            target = _clicked_actor(stage, event[0])
            observers = tuple(stage._clicks.get(None, ()))
            targeted = tuple(stage._clicks.get(target, ())) if target is not None else ()
            callbacks = (*observers, *targeted)
            for clicked in callbacks:
                if stage.running:
                    _trigger(stage, clicked, event)


def _clicked_actor(stage: Stage, position: Point) -> Actor | None:
    """Select one visible actor in render order using operation-local world bounds."""
    from .puppets import Puppet
    from .sprites import Sprite

    x, y = position[0] + stage.camera[0], position[1] + stage.camera[1]
    ordered = sorted(stage._members, key=lambda obj: obj.layer)
    for actor in reversed(ordered):
        if isinstance(actor, (Sprite, Puppet)) and actor.visible:
            bounds = actor.bounds
            if bounds.left <= x < bounds.right and bounds.bottom < y <= bounds.top:
                return actor
    return None


def advance(stage: Stage, now: float) -> None:
    """Advance at most five fixed steps; keep only fractional excess backlog."""
    previous = stage._last_wall
    stage._last_wall = now
    if stage.paused:
        _deliver(stage)
        dispatch(stage, simulation=False)
        return
    if previous is not None:
        stage._accumulator += min(0.25, max(0, now - previous))
    dt = 1 / stage.tick_rate
    steps = min(5, int((stage._accumulator + 1e-12) / dt))
    for _ in range(steps):
        if not stage.running or stage.paused:
            break
        stage._accumulator -= dt
        for slot, driver in tuple(stage._bots.items()):
            sample = driver(Event(stage, stage, dt))
            from .gamepads import GamepadInput

            if not isinstance(sample, GamepadInput):
                raise TypeError("An automated driver must return GamepadInput")
            _gamepads._apply(slot, sample)
        _deliver(stage)
        dispatch(stage)
        _gamepads._repeat(stage)
        _step(stage)
        if stage.paused:
            break
        for actor, callback in tuple(stage._updates):
            if stage.running and not stage.paused and (actor is None or actor._stage is stage):
                from .stage import _check_callback_result

                _check_callback_result(
                    cast(UpdateCallback, callback)(Event(stage, stage, dt))
                    if actor is None
                    else cast("ActorUpdateCallback[Actor]", callback)(Event(stage, actor, dt)),
                    "update",
                )
        if stage.running and not stage.paused:
            if stage._physics is not None:
                from ._physics import _integrate

                _integrate(stage, dt)
            stage._tick += 1
            _sample(stage)
    if stage._accumulator >= dt:
        stage._accumulator %= dt
    stage._accumulator = max(0, stage._accumulator)


async def drive(stage: Stage) -> None:
    """Yield every frame and always release resources on closure or callback failure."""
    try:
        for handler in tuple(stage._starts):
            _trigger(stage, handler)
        _step(stage)
        while stage.running:
            started = time.perf_counter()
            poll(stage)
            if not stage.running:
                break
            if stage._network is not None:
                from ._network import pump

                pump(stage, time.monotonic())
            advance(stage, started)
            stage._voices[:] = [voice for voice in stage._voices if not voice.finished]
            if stage.running:
                frame(stage)
            await asyncio.sleep(max(0, 1 / 60 - (time.perf_counter() - started)))
    finally:
        close(stage)


def close(stage: Stage) -> None:
    """Idempotently release this stage's resources, never someone else's display."""
    primary = sys.exception()
    errors: list[BaseException] = []
    stage._state = "closed"
    if stage._network is not None:
        from ._network import close as close_network

        try:
            close_network(
                stage,
                failed=primary is not None and not isinstance(primary, asyncio.CancelledError),
            )
        except BaseException as error:  # noqa: BLE001 -- finish independent cleanup, retain primary error
            errors.append(error)
    stage._remote_handlers.clear()
    stage._bots.clear()
    task = stage._task
    stage._task = None
    if task is not None:
        atexit.unregister(stage.stop)
        if task is not asyncio.current_task(loop=task.get_loop()):
            task.cancel()
    for root in tuple(stage._actions):
        try:
            _cancel(stage, root)
        except BaseException as error:  # noqa: BLE001 -- finish cleanup and re-raise the original failure
            errors.append(error)
    for obj in tuple(stage._members):
        try:
            stage.remove(obj)
        except BaseException as error:  # noqa: BLE001 -- finish cleanup and re-raise the original failure
            errors.append(error)
    if stage._physics is not None:
        from ._physics import _close

        try:
            _close(stage._physics)
        except BaseException as error:  # noqa: BLE001 -- finish native cleanup without masking the primary error
            errors.append(error)
    stage._messages.clear()
    stage._message_handlers.clear()
    stage._gamepad_handlers.clear()
    stage._starts.clear()
    stage._clone_handlers.clear()
    stage._clicks.clear()
    stage._updates.clear()
    stage._draws.clear()
    stage.stop_sounds()
    _clear_input(stage)
    try:
        _gamepads._close_devices(stage)
    except BaseException as error:  # noqa: BLE001 -- preserve primary failure and finish cleanup
        errors.append(error)
    if stage._target is not None:
        pygame.mixer.quit()
        pygame.font.quit()
        pygame.display.quit()
        stage._target = None
    if errors:
        if primary is not None:
            for cleanup_error in errors:
                primary.add_note(f"Cleanup also failed: {cleanup_error!r}")
        else:
            raise errors[0]
