"""A shared yielding driver; all retained execution state belongs to Stage."""

from __future__ import annotations

import asyncio
import platform
import sys
import time
import traceback
from importlib.resources import files
from typing import TYPE_CHECKING

import pygame

from ._render import frame
from ._scripts import _cancel, _deliver, _sample, _step, _trigger
from .errors import StageError
from .geometry import Point
from .input import Key, MouseButton

if TYPE_CHECKING:
    from ._commands import Actor
    from .stage import Stage


def start(stage: Stage) -> None:
    """Acquire one display, then block natively or schedule within the browser loop."""
    if stage._state != "new":
        raise StageError("A stage can run once; create a new Stage to start again")
    if pygame.display.get_surface() is not None:
        raise StageError("Another Pygame display is already active")
    if pygame.mixer.get_init() is not None:
        raise StageError("Another Pygame audio session is already active")
    if sys.platform != "emscripten":
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise StageError("Desktop run() requires a script outside an existing asyncio loop")
    try:
        pygame.display.init()
        if sys.platform != "emscripten":
            with files("plocks").joinpath("assets/icon.png").open("rb") as source:
                pygame.display.set_icon(pygame.image.load(source, "icon.png"))
            pygame.display.set_caption("Plocks")
        stage._target = pygame.display.set_mode((stage.width, stage.height))
        pygame.event.clear()
        if sys.platform == "emscripten":
            canvas = vars(platform)["window"].document.getElementById("canvas")
            canvas.style.width = f"min(100vw, 960px, calc(100vh * {stage.width / stage.height}))"
        stage._state = "running"
        if sys.platform == "emscripten":
            stage._task = asyncio.create_task(drive(stage))
        else:
            asyncio.run(drive(stage))
    except BaseException:
        pygame.display.quit()
        close(stage)
        raise


def _clear_input(stage: Stage) -> None:
    stage.keyboard._down.clear()
    stage.mouse._down.clear()
    stage._pending.clear()


def poll(stage: Stage) -> None:
    """Translate native events once; browser CSS scaling is handled by SDL."""
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            stage.stop()
        elif sys.platform != "emscripten" and event.type in (
            pygame.WINDOWFOCUSLOST,
            pygame.WINDOWHIDDEN,
            pygame.WINDOWMINIMIZED,
        ):
            _clear_input(stage)
            reason = {
                pygame.WINDOWFOCUSLOST: "focus",
                pygame.WINDOWHIDDEN: "hidden",
                pygame.WINDOWMINIMIZED: "minimized",
            }[event.type]
            stage._set_pause(reason, True)
        elif sys.platform != "emscripten" and event.type in (
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
        elif event.type in (pygame.KEYDOWN, pygame.KEYUP):
            _key(stage, event)
        elif event.type == pygame.MOUSEMOTION:
            stage.mouse._position = stage.from_screen(event.pos, world=False)
        elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            _mouse(stage, event)
    if sys.platform == "emscripten":
        window = vars(platform)["window"]
        suspended = bool(window.document.hidden) or not bool(window.document.hasFocus())
        if suspended:
            _clear_input(stage)
        stage._set_pause("application", suspended)


def _key(stage: Stage, event: pygame.event.Event) -> None:
    try:
        key = Key(pygame.key.name(event.key))
    except ValueError:
        return
    if event.type == pygame.KEYDOWN:
        if key not in stage.keyboard._down:
            stage._pending.append(key)
        stage.keyboard._down.add(key)
    else:
        stage.keyboard._down.discard(key)


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


def dispatch(stage: Stage) -> None:
    """Consume edge events once, with snapshot callback lists."""
    pending = tuple(stage._pending)
    stage._pending.clear()
    for event in pending:
        if not stage.running:
            break
        callbacks = tuple(stage._keys.get(event, ())) if isinstance(event, Key) else ()
        for callback in callbacks:
            if stage.running:
                _trigger(stage, callback)
        if not isinstance(event, Key):
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
        dispatch(stage)
        return
    if previous is not None:
        stage._accumulator += min(0.25, max(0, now - previous))
    dt = 1 / stage.tick_rate
    steps = min(5, int((stage._accumulator + 1e-12) / dt))
    for _ in range(steps):
        if not stage.running or stage.paused:
            break
        stage._accumulator -= dt
        _deliver(stage)
        dispatch(stage)
        _step(stage)
        if stage.paused:
            break
        for actor, callback in tuple(stage._updates):
            if stage.running and not stage.paused and (actor is None or actor._stage is stage):
                from .stage import _check_callback_result

                _check_callback_result(callback(dt), "update")
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
    """Yield every frame; report browser errors and always release owned resources."""
    try:
        for handler in tuple(stage._starts):
            _trigger(stage, handler)
        _step(stage)
        while stage.running:
            started = time.perf_counter()
            poll(stage)
            if not stage.running:
                break
            advance(stage, started)
            stage._voices[:] = [voice for voice in stage._voices if not voice.finished]
            if stage.running:
                frame(stage)
            delay = (
                0
                if sys.platform == "emscripten"
                else max(0, 1 / 60 - (time.perf_counter() - started))
            )
            await asyncio.sleep(delay)
    except Exception:
        if sys.platform == "emscripten":
            vars(platform)["window"].plocksError(traceback.format_exc())
        raise
    finally:
        close(stage)


def close(stage: Stage) -> None:
    """Idempotently release this stage's resources, never someone else's display."""
    primary = sys.exception()
    errors: list[BaseException] = []
    stage._state = "closed"
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
    stage._keys.clear()
    stage._starts.clear()
    stage._clicks.clear()
    stage._updates.clear()
    stage._draws.clear()
    stage.stop_sounds()
    _clear_input(stage)
    if stage._target is not None:
        pygame.mixer.quit()
        pygame.font.quit()
        pygame.display.quit()
        stage._target = None
    stage._task = None
    if errors:
        if primary is not None:
            for cleanup_error in errors:
                primary.add_note(f"Cleanup also failed: {cleanup_error!r}")
        else:
            raise errors[0]
