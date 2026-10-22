"""Modal UI participates in the existing simulation, input and cleanup lifecycle."""

from collections.abc import Callable, Iterator
from typing import cast

import pygame
import pytest

from plocks import (
    AlertLevel,
    Button,
    Canvas,
    Event,
    GamepadButton,
    GamepadPress,
    Image,
    Key,
    MouseButton,
    Panel,
    Sprite,
    Stage,
    StageError,
    UITheme,
)
from plocks._alerts import _layout
from plocks._render import frame
from plocks._runtime import advance, close, dispatch, poll


@pytest.fixture
def stage() -> Iterator[Stage]:
    """A real headless physical world for modal input, drawing and cleanup."""
    result = Stage(width=480, height=360, physics=True)
    result._state = "running"
    result._last_wall = 0
    result._target = pygame.display.set_mode((480, 360))
    yield result
    close(result)


def acknowledge(stage: Stage, slot: int = 0) -> None:
    """Use the real logical-button dispatch path, including other controllers."""
    stage._pending.append(GamepadPress(stage.gamepads[slot], GamepadButton.A))
    dispatch(stage)


def test_alert_pauses_physics_and_blocks_the_input_delivery_batch(stage: Stage) -> None:
    """The alert owns only its pause; pending/turbo edges cannot reach gameplay on dismissal."""
    hero = Sprite(Image.rectangle(20, 20), y=100)
    stage.add(hero)
    hero.body.velocity = (100, 0)
    calls: list[str] = []
    stage.on_button_down(GamepadButton.A)(lambda event: calls.append("jump"))
    stage.on_button_down(GamepadButton.SELECT)(lambda event: calls.append("restart"))
    stage.on_click(lambda event: calls.append("world"))
    stage._held_keys.add(Key.SPACE)
    stage.mouse._down.add(MouseButton.LEFT)

    def closed(event: Event[Stage, None]) -> None:
        assert event.target is stage and event.source is stage and event.data is None
        assert stage._alert is None and not stage.paused
        calls.append("closed")

    stage.alert("Game over!", level=AlertLevel.ERROR, on_close=closed)
    assert stage.paused and stage.gamepads[0].is_down(GamepadButton.A)
    assert stage.mouse.is_down(MouseButton.LEFT)
    before = (stage.time, hero.position)
    advance(stage, 10)
    assert (stage.time, hero.position) == before
    stage.resume()
    assert stage.paused
    stage._pending.extend(
        [
            GamepadPress(stage.gamepads[1], GamepadButton.A),
            GamepadPress(stage.gamepads[0], GamepadButton.SELECT),
            ((0, 0), MouseButton.LEFT),
        ]
    )
    dispatch(stage)
    assert calls == ["closed"] and not stage.paused
    advance(stage, 10.02)
    advance(stage, 10.04)
    assert hero.x > 0 and hero.y < before[1][1]


def test_existing_user_pause_and_suspended_focus_are_not_copied(stage: Stage) -> None:
    """Dismissal preserves user pause; hidden parent controls cannot regain stale focus."""
    panel = Panel()
    button = Button("Continue")
    panel.add(button)
    stage.add(panel)
    stage.focus(button)
    stage.pause()
    stage.alert("Paused already")
    assert stage.focused_button is button
    acknowledge(stage)
    assert stage.paused and stage.focused_button is button
    stage.resume()
    stage.alert("Hide the old menu")
    panel.visible = False
    acknowledge(stage)
    assert not stage.paused and stage.focused_button is None


def test_window_suspension_blocks_acknowledgment_and_survives_manual_resume(stage: Stage) -> None:
    """Focus/hidden reasons retain their existing behavior while the alert remains responsive afterward."""
    stage.alert("Hello")
    stage._set_pause("hidden", True)
    acknowledge(stage)
    assert stage._alert is not None and stage.paused
    stage.resume()
    assert stage.paused
    stage._set_pause("hidden", False)
    acknowledge(stage)
    assert stage._alert is None and not stage.paused


def test_native_event_translation_does_not_treat_an_alert_as_window_suspension(
    stage: Stage,
) -> None:
    """Mapped Space reaches the alert through pygame polling, instead of being cleared as hidden input."""
    stage.alert("Press Space")
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    poll(stage)
    dispatch(stage)
    assert stage._alert is None and not stage.paused


@pytest.mark.parametrize("level", tuple(AlertLevel))
def test_alert_levels_render_above_canvas_and_use_live_theme(
    stage: Stage, level: AlertLevel
) -> None:
    """Levels change the accent and visible heading without changing modality or camera coordinates."""
    stage.alert("A message\nwith a second line", level=level)
    alert = stage._alert
    assert alert is not None and stage.running
    panel, _, _, _, _ = _layout(stage, alert)
    stage.camera = (999, -300)

    @stage.on_draw
    def cover(canvas: Canvas) -> None:
        canvas.rectangle(stage.bounds, color="red")

    frame(stage)
    expected = {
        AlertLevel.INFO: stage.ui_theme.info_color,
        AlertLevel.WARNING: stage.ui_theme.warning_color,
        AlertLevel.SUCCESS: stage.ui_theme.success_color,
        AlertLevel.ERROR: stage.ui_theme.error_color,
    }
    assert stage._target is not None
    assert (
        stage._target.get_at((panel.left + 1, panel.centery))[:3]
        == pygame.Color(expected[level])[:3]
    )
    stage.ui_theme = UITheme(text_size=30, error_color="magenta")
    frame(stage)
    assert stage._alert is alert
    _, button, _, _, _ = _layout(stage, alert)
    stage._pending.append((stage.from_screen(button.center, world=False), MouseButton.LEFT))
    dispatch(stage)
    assert stage._alert is None and not stage.paused


def test_long_words_newlines_and_tiny_windows_fit_without_retained_layout(stage: Stage) -> None:
    """Long messages wrap/truncate locally and viewport-sized geometry remains bounded."""
    stage.alert("word" * 500 + "\n\nMore text", button_text="Continue " * 100)
    alert = stage._alert
    assert alert is not None
    panel, button, font, lines, padding = _layout(stage, alert)
    assert panel.left >= 0 and panel.right <= stage.width
    assert panel.top >= 0 and panel.bottom <= stage.height
    assert panel.contains(button) and lines[-1].endswith("...")
    assert all(font.size(line)[0] <= panel.width - 2 * padding for line in lines)
    frame(stage)
    acknowledge(stage)
    tiny = Stage(width=8, height=8)
    try:
        tiny._state = "running"
        tiny.alert("Long message", button_text="OK")
        tiny._target = pygame.Surface((8, 8))
        assert tiny._alert is not None
        _layout(tiny, tiny._alert)
    finally:
        # Do not let an unrelated scratch target retire the fixture's active display.
        tiny._target = None
        close(tiny)


def test_reopened_alert_does_not_consume_a_previous_dialogs_second_press(stage: Stage) -> None:
    """An acknowledgment callback can open the next alert, requiring a fresh input cycle."""
    stage.alert("First", on_close=lambda event: stage.alert("Second"))
    stage._pending.extend(GamepadPress(stage.gamepads[0], GamepadButton.A) for _ in range(2))
    dispatch(stage)
    assert stage._alert is not None and stage._alert.text == "Second"
    acknowledge(stage)
    assert stage._alert is None


def test_alert_validation_preserves_state_and_rejects_async_callback(stage: Stage) -> None:
    """Bad levels/callbacks/labels do not pause or create a half-admitted modal."""
    with pytest.raises(TypeError):
        stage.alert("Oops", level=cast(AlertLevel, "warning"))
    with pytest.raises(ValueError):
        stage.alert("Oops", button_text="\n")
    with pytest.raises(ValueError):
        stage.alert("Oops", button_text=" ")

    async def async_callback(event: Event[Stage, None]) -> None:
        pass

    with pytest.raises(TypeError):
        stage.alert("Oops", on_close=cast(Callable[[Event[Stage, None]], None], async_callback))
    assert stage._alert is None and not stage.paused
    stage.alert("")
    original = stage._alert
    with pytest.raises(StageError):
        stage.alert("Second")
    assert stage._alert is original


def test_closure_discards_modal_without_invoking_callback(stage: Stage) -> None:
    """Modal resources belong to the stage; shutdown never acts like acknowledgment."""
    called: list[None] = []
    stage.alert("Bye", on_close=lambda event: called.append(None))
    close(stage)
    close(stage)
    assert not called and stage._alert is None and "alert" not in stage._pause_reasons


def test_alert_callback_failure_retains_traceback_and_cleans_stage() -> None:
    """The existing outer driver observes on_close exceptions and performs complete cleanup."""
    stage = Stage()
    panel, button = Panel(), Button("Menu")
    panel.add(button)
    stage.add(panel)
    failure = RuntimeError("alert callback failed")

    def fail(event: Event[Stage, None]) -> None:
        raise failure

    @stage.on_start
    def open_alert(event: Event[Stage, None]) -> None:
        stage.alert("Oops", on_close=fail)
        stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.A))

    with pytest.raises(RuntimeError) as captured:
        stage.run()
    assert captured.value is failure
    assert stage._alert is None and not stage.objects and not stage._voices and not stage._actions
    assert button._stage is None and panel._stage is None


def test_held_controller_state_does_not_become_a_false_new_press(stage: Stage) -> None:
    """Preserving the source sample avoids synthetic press edges after modal dismissal."""
    from plocks import GamepadInput
    from plocks._gamepads import _apply

    log: list[str] = []
    stage.on_button_down(GamepadButton.A)(lambda event: log.append("game"))
    stage.alert("Press A")
    sample = GamepadInput(buttons=frozenset({GamepadButton.A}))
    _apply(stage.gamepads[0], sample)
    dispatch(stage)
    assert stage._alert is None
    _apply(stage.gamepads[0], sample)
    dispatch(stage)
    assert not log
    _apply(stage.gamepads[0], GamepadInput())
    _apply(stage.gamepads[0], sample)
    dispatch(stage)
    assert log == ["game"]
