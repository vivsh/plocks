"""Themed, anchored and grouped controls share drawing and input geometry."""

from collections.abc import Iterator

import pygame
import pytest

from plocks import Anchor, Button, Event, Label, Panel, ProgressBar, Stage, StageError, UITheme
from plocks._render import frame
from plocks._runtime import close, dispatch
from plocks._ui import _hit
from plocks._ui_layout import _control_rect


@pytest.fixture
def stage() -> Iterator[Stage]:
    """A running logical-pixel window with full ordinary runtime cleanup."""
    result = Stage(width=480, height=360, background="black", ui_theme=UITheme(corner_radius=0))
    result._state = "running"
    result._target = pygame.display.set_mode((480, 360))
    yield result
    close(result)


@pytest.mark.parametrize("anchor", tuple(Anchor))
def test_each_anchor_uses_the_painted_button_rectangle(stage: Stage, anchor: Anchor) -> None:
    """Every named pivot gives mouse input exactly the same rectangle as drawing."""
    button = Button("Go", position=(-20, 30), width=80, height=40, anchor=anchor)
    stage.add(button)
    rect = _control_rect(stage, button)
    ax, ay = anchor.value
    assert rect.topleft == (round(220 - 80 * ax), round(150 - 40 * ay))
    assert _hit(stage, stage.from_screen(rect.center, world=False)) is button
    assert _hit(stage, stage.from_screen((rect.right, rect.centery), world=False)) is None
    stage.camera = (999, -500)
    assert _control_rect(stage, button) == rect
    frame(stage)
    assert stage._target is not None
    assert (
        stage._target.get_at((rect.left + 4, rect.top + 4))[:3]
        == pygame.Color(stage.ui_theme.button_color)[:3]
    )


def test_live_theme_and_explicit_overrides(stage: Stage) -> None:
    """Only overrides are retained; live theme replacement and resetting None use the current stage."""
    label = Label("Score: 1", anchor=Anchor.TOP_LEFT)
    fixed = Label("Fixed", color="gold", size=18)
    button = Button("Go")
    bar = ProgressBar(value=50, width=100, height=20)
    for control in (label, fixed, button, bar):
        stage.add(control)
    stage.ui_theme = UITheme(text_color="red", accent_color="blue", text_size=30)
    assert label.color == "red" and label.size == 30 and button.text_size == 30
    assert fixed.color == "gold" and fixed.size == 18 and bar.color == "blue"
    bar.color = "orange"
    stage.ui_theme = UITheme(text_color="cyan", accent_color="green", text_size=26)
    assert bar.color == "orange" and label.size == 26
    bar.color = None
    label.color = None
    label.size = None
    button.text_size = None
    assert bar.color == "green" and label.color == "cyan" and button.text_size == 26
    frame(stage)


def test_label_growth_keeps_its_selected_edge(stage: Stage) -> None:
    """Changing text changes measured size without retaining or moving its anchored edge."""
    label = Label("9\nx", position=(-200, 150), anchor=Anchor.TOP_LEFT)
    stage.add(label)
    before = _control_rect(stage, label)
    label.text = "100000\nx"
    after = _control_rect(stage, label)
    assert after.topleft == before.topleft and after.width > before.width
    label.anchor = Anchor.BOTTOM_RIGHT
    assert _control_rect(stage, label).bottomright == (40, 30)


def test_panel_attachment_clipping_movement_and_readding(stage: Stage) -> None:
    """One parent owns children; local geometry follows it and clipped pixels cannot receive clicks."""
    panel = Panel(position=(30, 0), width=120, height=100)
    button = Button("Go", position=(50, 0), width=80, height=40)
    panel.add(button)
    with pytest.raises(StageError):
        stage.add(button)
    stage.add(panel)
    assert stage.objects == (panel,) and panel.children == (button,)
    assert button._stage is stage
    assert _hit(stage, (80, 0)) is button
    assert _hit(stage, (110, 0)) is None
    stage.focus(button)
    panel.position = (-100, 20)
    assert button.position == (50, 0)
    assert _hit(stage, (-50, 20)) is button
    panel.visible = False
    assert stage.focused_button is None and _hit(stage, (-50, 20)) is None
    with pytest.raises(StageError):
        stage.focus(button)
    assert button.visible
    panel.visible = True
    stage.focus(button)
    stage.remove(panel)
    assert button._stage is None and button._panel is panel and stage.focused_button is None
    stage.add(panel)
    assert button._stage is stage
    panel.remove(button)
    assert button._stage is None and button._panel is None
    stage.add(button)
    assert button in stage.objects


def test_panel_alpha_and_child_button_use_local_coordinates(stage: Stage) -> None:
    """A translucent fill composites without changing children or leaking drawing outside the panel."""
    panel = Panel(width=100, height=60, color=(200, 0, 0, 128))
    button = Button("", position=(60, 0), width=80, height=30)
    panel.add(button)
    stage.add(panel)
    frame(stage)
    assert stage._target is not None
    assert stage._target.get_at((195, 180))[:3] == (100, 0, 0)
    assert stage._target.get_at((295, 180))[:3] == (0, 0, 0)
    calls: list[Button] = []

    @button.on_click
    def clicked(event: Event[Button, None]) -> None:
        calls.append(event.target)

    from plocks import MouseButton

    stage._pending.append(((40, 0), MouseButton.LEFT))
    dispatch(stage)
    assert calls == [button]


def test_panel_parenting_rejects_nesting_and_duplicate_owners(stage: Stage) -> None:
    """Bad membership changes leave both containers and existing root attachments intact."""
    panel, other = Panel(), Panel()
    label = Label("Hello")
    panel.add(label)
    with pytest.raises(ValueError):
        panel.add(label)
    with pytest.raises(StageError):
        other.add(label)
    stage.add(panel)
    with pytest.raises(TypeError):
        panel.add(other)  # type: ignore[arg-type]  # Runtime protection for untyped callers.
    with pytest.raises(ValueError):
        stage.remove(label)
    panel.clear()
    assert not panel.children and label._stage is None and label._panel is None


def test_theme_and_anchor_validation_before_mutation(stage: Stage) -> None:
    """Invalid theme values, overrides or named anchors preserve the prior valid setting."""
    with pytest.raises(ValueError):
        UITheme(text_size=0)
    with pytest.raises(ValueError):
        UITheme(padding=-1)
    with pytest.raises(TypeError):
        UITheme(corner_radius=True)
    label = Label("Hello")
    stage.add(label)
    with pytest.raises(ValueError):
        label.size = 0
    assert label.size == stage.ui_theme.text_size


def test_panel_resize_releases_clipped_focus_and_bounds_scratch_surfaces(stage: Stage) -> None:
    """Geometry changes invalidate unavailable focus; large overlays allocate only visible pixels."""
    panel = Panel(width=160, height=100)
    button = Button("Go", position=(50, 0), width=30)
    panel.add(button)
    stage.add(panel)
    stage.focus(button)
    panel.width = 40
    assert stage.focused_button is None
    with pytest.raises(StageError):
        stage.focus(button)
    stage.remove(panel)
    huge = Panel(width=1_000_000, height=1_000_000, color="red")
    stage.add(huge)
    frame(stage)
    assert stage._target is not None
    assert stage._target.get_at((0, 0))[:3] == (255, 0, 0)
