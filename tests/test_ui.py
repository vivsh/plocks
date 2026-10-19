"""Persistent screen controls use one stage membership and focus owner."""

from collections.abc import Iterator
from pathlib import Path

import pygame
import pytest

from plocks import (
    Button,
    Canvas,
    GamepadButton,
    GamepadPress,
    Label,
    MouseButton,
    ProgressBar,
    Sprite,
    Stage,
    StageError,
)
from plocks._render import frame
from plocks._runtime import advance, close, dispatch

IMAGE = Path(__file__).parent / "fixtures/games/state_proof/assets/hero.png"


@pytest.fixture
def stage() -> Iterator[Stage]:
    """A running headless world for input and selected-pixel assertions."""
    result = Stage(width=200, height=100)
    result._target = pygame.display.set_mode((result.width, result.height))
    result._state = "running"
    result._last_wall = 0
    yield result
    close(result)


def test_meter_validation_and_button_membership(stage: Stage) -> None:
    """Invalid assignments preserve values, and controls attach only once."""
    bar = ProgressBar(value=50)
    with pytest.raises(ValueError):
        bar.maximum = 40
    assert bar.maximum == 100 and bar.value == 50
    with pytest.raises(ValueError):
        bar.value = float("nan")
    with pytest.raises(ValueError):
        bar.value = 200
    button = Button("Go")
    with pytest.raises(ValueError):
        button.text = "two\nlines"
    stage.add(button)
    with pytest.raises(ValueError):
        stage.add(button)
    other = Stage()
    try:
        with pytest.raises(StageError):
            other.add(button)
    finally:
        close(other)
    stage.focus(button)
    button.enabled = False
    assert stage.focused_button is None
    button.enabled = True
    stage.focus(button)
    button.visible = False
    assert stage.focused_button is None
    button.visible = True
    stage.focus(button)
    stage.remove(button)
    assert button._stage is None and stage.focused_button is None


def test_topmost_disabled_button_consumes_world_click_but_observer_sees_it(stage: Stage) -> None:
    """UI hit ownership prevents click-through without falsifying mouse input."""
    actor = Sprite(IMAGE)
    button = Button("Disabled")
    stage.add(actor)
    stage.add(button)
    called: list[str] = []
    actor.on_click(lambda event: called.append("actor"))
    stage.on_click(lambda event: called.append("stage"))
    button.on_click(lambda event: called.append("button"))
    button.enabled = False
    stage._pending.append(((0, 0), MouseButton.LEFT))
    dispatch(stage)
    assert called == ["stage"]
    button.enabled = True
    stage._pending.append(((0, 0), MouseButton.LEFT))
    dispatch(stage)
    assert called == ["stage", "stage", "button"]
    assert stage.focused_button is button


def test_menu_focus_navigates_both_slots_and_suppresses_gameplay_turbo(stage: Stage) -> None:
    """Logical UI navigation consumes edges and existing repeats without another timer."""
    first, second = Button("First"), Button("Second", layer=1)
    stage.add(first)
    stage.add(second)
    log: list[str] = []
    first.on_click(lambda event: log.append("first"))
    second.on_click(lambda event: log.append("second"))
    stage.on_button_down(GamepadButton.A, repeat=0.01)(lambda event: log.append("game"))
    stage.focus(first)
    stage._pending.extend(
        (
            GamepadPress(stage.gamepads[1], GamepadButton.DOWN),
            GamepadPress(stage.gamepads[0], GamepadButton.A),
        )
    )
    dispatch(stage)
    assert log == ["second"] and stage.focused_button is second
    stage.pause()
    stage._pending.append(GamepadPress(stage.gamepads[1], GamepadButton.A))
    advance(stage, 0.1)
    assert log == ["second", "second"]
    stage._set_pause("hidden", True)
    stage._pending.append(GamepadPress(stage.gamepads[1], GamepadButton.A))
    advance(stage, 0.2)
    assert log == ["second", "second"]
    stage._set_pause("hidden", False)
    stage.focus(None)
    stage._pending.append(GamepadPress(stage.gamepads[1], GamepadButton.A))
    dispatch(stage)
    assert log[-1] == "game"


def test_screen_controls_ignore_camera_and_canvas_remains_on_top(stage: Stage) -> None:
    """Meters render their ratio in screen space and preserve the overlay escape hatch."""
    stage.camera = (1234, -500)
    bar = ProgressBar(value=50, maximum=100, position=(0, 0), width=100, height=20, color="blue")
    label = Label("Score\n0", position=(0, 35))
    stage.add(bar)
    stage.add(label)
    frame(stage)
    assert stage._target is not None
    assert stage._target.get_at((70, 50))[:3] == (0, 0, 255)
    assert stage._target.get_at((130, 50))[:3] == pygame.Color("#293340")[:3]

    @stage.on_draw
    def cover(canvas: Canvas) -> None:
        canvas.circle((0, 0), 3, color="red")

    frame(stage)
    assert stage._target.get_at((100, 50))[:3] == (255, 0, 0)


def test_button_exception_closes_controls_without_masking_failure() -> None:
    """A synchronous menu callback failure is observed by the existing outer driver."""
    from plocks import Event

    stage = Stage()
    button = Button("Fail")
    stage.add(button)
    stage.focus(button)
    failure = RuntimeError("menu failed")

    @button.on_click
    def fail(event: Event[Button, None]) -> None:
        raise failure

    @stage.on_start
    def click(event: Event[Stage, None]) -> None:
        stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.A))

    with pytest.raises(RuntimeError) as captured:
        stage.run()
    assert captured.value is failure
    assert button._stage is None and stage.focused_button is None and not stage.objects
