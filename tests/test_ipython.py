"""Interactive driver ownership, preflight checks and lifecycle failure recovery."""

import asyncio
import atexit
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock, patch

import pygame
import pytest

from plocks import Event, GamepadButton, Key, Sound, Sprite, Stage, StageError


@pytest.fixture
def console(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[Stage, Mock, asyncio.AbstractEventLoop]]:
    """Use a real asyncio loop and typed shell identity; terminal behavior is tested separately."""
    from IPython.terminal.interactiveshell import TerminalInteractiveShell

    shell = Mock(spec=TerminalInteractiveShell)
    shell.simple_prompt = False
    shell.active_eventloop = None
    loop = asyncio.new_event_loop()
    monkeypatch.setattr("IPython.get_ipython", lambda: shell)
    monkeypatch.setattr("IPython.core.async_helpers.get_asyncio_loop", lambda: loop)
    stage = Stage()
    stage.gamepads[0].map_key(Key.RIGHT, GamepadButton.RIGHT)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    try:
        yield stage, shell, loop
    finally:
        stage.stop()
        for task in asyncio.all_tasks(loop):
            task.cancel()
        loop.run_until_complete(asyncio.sleep(0))
        loop.close()


def test_stop_before_first_turn_closes_resources_and_retires_task(
    console: tuple[Stage, Mock, asyncio.AbstractEventLoop],
) -> None:
    """A never-started coroutine cannot clean itself; prompt stop handles that path."""
    stage, shell, loop = console
    stage.run(interactive=True)
    task = stage._task
    assert task is not None and not task.done() and stage.running
    stage.stop()
    stage.stop()
    assert task.done() and task.cancelled() and stage._task is None
    assert not asyncio.all_tasks(loop) and pygame.display.get_surface() is None
    shell.showtraceback.assert_not_called()
    with pytest.raises(StageError, match="once"):
        stage.run(interactive=True)


def test_stop_from_callback_waits_for_safe_driver_cleanup(
    console: tuple[Stage, Mock, asyncio.AbstractEventLoop],
) -> None:
    """Stopping in update neither invalidates the callback's live canvas nor leaves its task."""
    stage, shell, loop = console

    @stage.on_update
    def finished(event: Event[Stage, float]) -> None:
        stage.stop()
        assert stage._target is not None

    stage.run(interactive=True)
    task = stage._task
    loop.run_until_complete(asyncio.sleep(0.04))
    assert task is not None and task.done() and task.exception() is None
    assert stage._task is None and stage._target is None
    shell.showtraceback.assert_not_called()


def test_external_cancellation_retires_actions_actors_and_audio(
    console: tuple[Stage, Mock, asyncio.AbstractEventLoop],
) -> None:
    """Canceling the outer driver freezes/retire scripts and invalidates every voice."""
    stage, shell, loop = console
    hero = Sprite(Path(__file__).parents[1] / "src/plocks/_games/platformer/assets/hero.png")
    stage.add(hero)
    stage.run(interactive=True)
    action = hero.glide_by(x=100, seconds=5)
    hero.say("Hello", seconds=5)
    sound = Sound(Path(__file__).parent / "fixtures/games/proof/assets/tone.ogg")
    voice = stage.play(sound, loop=True)
    loop.run_until_complete(asyncio.sleep(0.03))
    task = stage._task
    assert task is not None and not action.done
    task.cancel()
    loop.run_until_complete(asyncio.sleep(0))
    assert task.cancelled() and stage._task is None
    assert action.cancelled and hero._stage is None and voice.finished
    assert not stage.objects and not stage._actions and not stage._voices
    assert not stage._pending and not stage._messages and stage._target is None
    shell.showtraceback.assert_not_called()


@pytest.mark.parametrize("event", ["start", "update", "draw", "key"])
def test_original_callback_error_is_observed_after_complete_cleanup(
    event: str, console: tuple[Stage, Mock, asyncio.AbstractEventLoop]
) -> None:
    """Every driver callback failure reports its original error and traceback to IPython."""
    stage, shell, loop = console
    error = LookupError(f"{event} failure")

    def fail(argument: object) -> None:
        raise error

    if event == "start":
        stage.on_start(fail)
    elif event == "update":
        stage.on_update(fail)
    elif event == "draw":
        stage.on_draw(fail)
    else:
        stage.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])(fail)
    stage.run(interactive=True)
    task = stage._task
    if event == "key":
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    loop.run_until_complete(asyncio.sleep(0.05))
    assert task is not None and task.done() and task.exception() is error
    shell.showtraceback.assert_called_once()
    displayed = shell.showtraceback.call_args.args[0]
    assert displayed[0] is LookupError and displayed[1] is error and displayed[2] is not None
    assert stage._state == "closed" and stage._target is None and stage._task is None
    assert not asyncio.all_tasks(loop)


def test_interactive_focus_policy_keeps_hide_and_user_pause_independent(
    console: tuple[Stage, Mock, asyncio.AbstractEventLoop],
) -> None:
    """Focus clears keys without suspension; hide/minimize and user pause still freeze time."""
    stage, _, loop = console
    stage.run(interactive=True)
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
    pygame.event.post(pygame.event.Event(pygame.WINDOWFOCUSLOST))
    loop.run_until_complete(asyncio.sleep(0.03))
    assert not stage.paused and not stage.gamepads[0].is_down(GamepadButton.RIGHT)
    stage.pause()
    pygame.event.post(pygame.event.Event(pygame.WINDOWHIDDEN))
    pygame.event.post(pygame.event.Event(pygame.WINDOWMINIMIZED))
    loop.run_until_complete(asyncio.sleep(0.02))
    frozen = stage.time
    stage.resume()
    pygame.event.post(pygame.event.Event(pygame.WINDOWSHOWN))
    loop.run_until_complete(asyncio.sleep(0.02))
    assert stage.paused and stage.time == frozen
    pygame.event.post(pygame.event.Event(pygame.WINDOWRESTORED))

    async def wait_for_resume() -> None:
        async with asyncio.timeout(1):
            while stage.paused or stage.time <= frozen:
                await asyncio.sleep(0.005)

    loop.run_until_complete(wait_for_resume())
    assert not stage.paused and stage.time > frozen


def test_rejected_second_stage_preserves_original_driver(
    console: tuple[Stage, Mock, asyncio.AbstractEventLoop],
) -> None:
    """A conflicting run never steals another stage's target or task."""
    stage, _, _ = console
    stage.run(interactive=True)
    task, target = stage._task, stage._target
    with pytest.raises(StageError, match="display"):
        Stage().run(interactive=True)
    assert stage.running and stage._task is task and pygame.display.get_surface() is target
    stage.stop()
    other = Stage()
    other.gamepads[0].map_key(Key.RIGHT, GamepadButton.RIGHT)
    other.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    try:
        other.run(interactive=True)
        assert other.running
    finally:
        other.stop()


@pytest.mark.parametrize("kind", ["plain", "notebook", "simple", "other_gui"])
def test_unsupported_context_is_rejected_before_opening_a_window(
    kind: str,
    console: tuple[Stage, Mock, asyncio.AbstractEventLoop],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unsupported shells and GUI loops fail without creating or closing native resources."""
    stage, shell, _ = console
    if kind == "plain":
        monkeypatch.setattr("IPython.get_ipython", lambda: None)
    elif kind == "notebook":
        monkeypatch.setattr("IPython.get_ipython", lambda: object())
    elif kind == "simple":
        shell.simple_prompt = True
    else:
        shell.active_eventloop = "qt"
    with pytest.raises(StageError):
        stage.run(interactive=True)
    assert stage._state == "new" and stage._task is None and not pygame.display.get_init()
    shell.enable_gui.assert_not_called()


def test_optional_dependency_failure_is_actionable_without_affecting_blocking_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """IPython is imported only by the opt-in path; a plain game still runs without it."""
    monkeypatch.setitem(sys.modules, "IPython", None)
    stage = Stage()
    stage.gamepads[0].map_key(Key.RIGHT, GamepadButton.RIGHT)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    with pytest.raises(StageError, match="pip install"):
        stage.run(interactive=True)
    assert stage._state == "new" and not pygame.display.get_init()

    @stage.on_update
    def stop(event: Event[Stage, float]) -> None:
        stage.stop()

    stage.run()
    assert stage._target is None


def test_foreign_running_loop_is_not_adopted(
    console: tuple[Stage, Mock, asyncio.AbstractEventLoop],
) -> None:
    """A transient async runner cannot accidentally become the interactive scheduling owner."""
    stage, shell, _ = console

    async def attempt() -> None:
        with pytest.raises(StageError, match="normal IPython command"):
            stage.run(interactive=True)

    asyncio.run(attempt())
    assert stage._state == "new" and stage._target is None
    shell.enable_gui.assert_not_called()


def test_partial_native_startup_failure_closes_stage(
    console: tuple[Stage, Mock, asyncio.AbstractEventLoop], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed window acquisition leaves no partial interactive stage or queued driver."""
    stage, _, loop = console

    def fail(size: object) -> None:
        raise OSError("display unavailable")

    monkeypatch.setattr(pygame.display, "set_mode", fail)
    with pytest.raises(OSError, match="display unavailable"):
        stage.run(interactive=True)
    assert stage._state == "closed" and stage._task is None and stage._target is None
    assert not asyncio.all_tasks(loop) and not pygame.display.get_init()


def test_failed_task_admission_closes_unstarted_coroutine_and_resources(
    console: tuple[Stage, Mock, asyncio.AbstractEventLoop], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Task-factory failures propagate without leaking the new window or an unawaited coroutine."""
    stage, _, loop = console

    def fail(coroutine: object, *, name: str) -> None:
        raise RuntimeError("task factory failed")

    with monkeypatch.context() as context:
        context.setattr(loop, "create_task", fail)
        with pytest.raises(RuntimeError, match="task factory failed"):
            stage.run(interactive=True)
    assert stage._state == "closed" and stage._target is None and stage._task is None


@pytest.mark.skipif(sys.platform == "win32", reason="The real-terminal harness uses POSIX PTYs")
@pytest.mark.parametrize("simple", [False, True])
def test_real_terminal_ipython_session(tmp_path: Path, simple: bool) -> None:
    """Live terminal editing, Ctrl-C, original tracebacks and exit cleanup work together."""
    arguments = [
        sys.executable,
        str(Path(__file__).with_name("ipython_terminal.py")),
        "--output",
        str(tmp_path),
    ]
    if simple:
        arguments.append("--simple")
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "IPYTHON_TERMINAL_OK" in result.stdout


def test_prompt_cleanup_does_not_reenter_a_foreign_running_loop(
    console: tuple[Stage, Mock, asyncio.AbstractEventLoop],
) -> None:
    """Stop releases native resources even when called inside another transient async helper."""
    stage, _, loop = console
    stage.run(interactive=True)
    task = stage._task

    async def stop() -> None:
        stage.stop()
        assert stage._task is None and stage._target is None

    asyncio.run(stop())
    loop.run_until_complete(asyncio.sleep(0))
    assert task is not None and task.done() and not asyncio.all_tasks(loop)


def test_closed_stages_unregister_their_exit_callbacks(
    console: tuple[Stage, Mock, asyncio.AbstractEventLoop],
) -> None:
    """Repeated interactive sessions do not keep retired stages in the interpreter exit registry."""
    stage, _, loop = console
    with (
        patch("atexit.register", wraps=atexit.register) as register,
        patch("atexit.unregister", wraps=atexit.unregister) as unregister,
    ):
        for current in (stage, Stage(), Stage()):
            current.run(interactive=True)
            current.stop()
        assert register.call_count == unregister.call_count == 3
        assert [call.args for call in register.call_args_list] == [
            call.args for call in unregister.call_args_list
        ]
    assert not asyncio.all_tasks(loop)


def test_traceback_formatter_failure_preserves_the_game_error(
    console: tuple[Stage, Mock, asyncio.AbstractEventLoop], capsys: pytest.CaptureFixture[str]
) -> None:
    """An unavailable IPython formatter still prints the original exception without a task warning."""
    stage, shell, loop = console
    shell.showtraceback.side_effect = RuntimeError("formatter unavailable")

    @stage.on_start
    def fail(event: Event[Stage, None]) -> None:
        raise ValueError("original game failure")

    stage.run(interactive=True)
    loop.run_until_complete(asyncio.sleep(0))
    output = capsys.readouterr().err
    assert "ValueError: original game failure" in output
    assert "Exception in callback" not in output
    assert stage._task is None and stage._target is None


def test_interactive_start_rejects_non_main_thread_without_creating_one(
    console: tuple[Stage, Mock, asyncio.AbstractEventLoop], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The native main-thread constraint is checked before acquiring display resources."""
    stage, shell, _ = console
    monkeypatch.setattr("plocks._ipython.current_thread", lambda: object())
    with pytest.raises(StageError, match="main thread"):
        stage.run(interactive=True)
    assert stage._state == "new" and stage._target is None
    shell.enable_gui.assert_not_called()


def test_exit_registration_failure_cancels_the_admitted_task(
    console: tuple[Stage, Mock, asyncio.AbstractEventLoop], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failure after task admission retires that task without closing its coroutine twice."""
    stage, _, loop = console

    def fail(callback: object) -> None:
        raise RuntimeError("exit registration failed")

    monkeypatch.setattr("plocks._ipython.atexit.register", fail)
    with pytest.raises(RuntimeError, match="exit registration failed"):
        stage.run(interactive=True)
    assert stage._task is None and stage._target is None and not stage.running
    assert not asyncio.all_tasks(loop)


def test_external_cancellation_before_first_turn_still_closes_stage(
    console: tuple[Stage, Mock, asyncio.AbstractEventLoop],
) -> None:
    """Completion owns the cleanup fallback when cancellation skips the entire coroutine body."""
    stage, shell, loop = console
    hero = Sprite(Path(__file__).parents[1] / "src/plocks/_games/platformer/assets/hero.png")
    stage.add(hero)
    stage.run(interactive=True)
    action = hero.glide_by(x=100, seconds=1)
    voice = stage.play(Sound(Path(__file__).parent / "fixtures/games/proof/assets/tone.ogg"))
    task = stage._task
    assert task is not None
    task.cancel()
    loop.run_until_complete(asyncio.sleep(0))
    assert task.cancelled() and stage._task is None and stage._target is None
    assert stage._state == "closed" and action.cancelled and voice.finished
    assert hero._stage is None and not stage.objects and not stage._actions
    shell.showtraceback.assert_not_called()


def test_early_cancellation_cleanup_errors_are_reported(
    console: tuple[Stage, Mock, asyncio.AbstractEventLoop], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pre-start cancellation fallback observes cleanup errors instead of losing them in callbacks."""
    from plocks import _gamepads

    stage, shell, loop = console
    original = _gamepads._close_devices
    error = OSError("controller close failed")

    def close_devices(owner: Stage) -> None:
        original(owner)
        raise error

    stage.run(interactive=True)
    task = stage._task
    assert task is not None
    monkeypatch.setattr(_gamepads, "_close_devices", close_devices)
    task.cancel()
    loop.run_until_complete(asyncio.sleep(0))
    assert stage._task is None and stage._target is None
    assert shell.showtraceback.call_args.args[0][1] is error
