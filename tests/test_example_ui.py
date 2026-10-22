"""Play the bundled games' actual screen controls, without duplicating game rules."""

import runpy
from pathlib import Path
from typing import cast

import pygame

from plocks import (
    AlertLevel,
    Button,
    Event,
    GamepadButton,
    GamepadPress,
    Label,
    MouseButton,
    Panel,
    Sprite,
    Stage,
)
from plocks._render import frame
from plocks._runtime import advance, close
from plocks._scripts import _step, _trigger
from plocks._ui_layout import _control_rect

ROOT = Path(__file__).parents[1] / "src/plocks/_games"


def test_maze_panels_resume_and_completion_alert_keeps_world_independent() -> None:
    """A real pause button resumes patrol; collecting coins opens a themed success modal."""
    values = runpy.run_path(str(ROOT / "maze_quest/main.py"))
    stage = cast(Stage, values["stage"])
    menu, hud = cast(Panel, values["menu"]), cast(Panel, values["hud"])
    resume = cast(Button, values["resume"])
    enemy = cast(Sprite, values["enemy"])
    stage._state = "running"
    stage._last_wall = 0
    stage._target = pygame.display.set_mode((stage.width, stage.height))
    try:
        for handler in tuple(stage._starts):
            _trigger(stage, handler)
        _step(stage)
        start = enemy.x
        advance(stage, 0.1)
        assert enemy.x > start and hud.children == (values["score"], values["health"])
        assert resume in menu.children and resume not in stage.objects
        stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.START))
        advance(stage, 0.2)
        assert stage.paused and menu.visible and stage.focused_button is resume
        position, time = enemy.position, stage.time
        frame(stage)
        assert stage._target.get_at((320, 140))[:3] == (36, 55, 75)
        stage._pending.append(
            (stage.from_screen(_control_rect(stage, resume).center, world=False), MouseButton.LEFT)
        )
        advance(stage, 0.3)
        assert not stage.paused and not menu.visible and stage.focused_button is None
        advance(stage, 0.4)
        advance(stage, 0.5)
        assert enemy.position != position and stage.time > time
        coins = [item.other for item in stage._touches[:4]]
        collect = values["collect"]
        assert callable(collect)
        for coin in coins:
            assert isinstance(coin, Sprite)
            collect(Event(stage, values["hero"], coin))
        assert stage._alert is not None and stage._alert.level is AlertLevel.SUCCESS
        assert cast(Label, values["score"]).text == "Coins: 4 / 4"
        frozen = enemy.position, stage.time
        advance(stage, 0.6)
        frame(stage)
        assert (enemy.position, stage.time) == frozen
        stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.A))
        advance(stage, 0.7)
        assert stage._alert is None and not stage.paused
    finally:
        close(stage)
    assert all(control._stage is None for control in (*hud.children, *menu.children))


def test_readme_dashboard_clicks_fill_bar_and_acknowledge_alert(tmp_path: Path) -> None:
    """The exact asset-free README program runs and responds through the real UI dispatcher."""
    readme = (ROOT.parents[2] / "README.md").read_text()
    snippet = (
        readme.split("## 🎛️ Give your game a dashboard", 1)[1]
        .split("```python", 1)[1]
        .split("```", 1)[0]
    )
    entry = tmp_path / "main.py"
    entry.write_text(snippet)
    values = runpy.run_path(str(entry))
    stage = cast(Stage, values["stage"])
    button = cast(Button, values["collect"])
    stage._state = "running"
    stage._last_wall = 0
    stage._target = pygame.display.set_mode((stage.width, stage.height))
    try:
        position = stage.from_screen(_control_rect(stage, button).center, world=False)
        for count in range(1, 4):
            stage._pending.append((position, MouseButton.LEFT))
            advance(stage, count * 0.1)
            frame(stage)
            assert cast(Label, values["score"]).text == f"Coins: {count}"
        assert not button.enabled and stage.paused
        assert stage._alert is not None and stage._alert.level is AlertLevel.SUCCESS
        frozen = stage.time
        advance(stage, 0.4)
        assert stage.time == frozen
        stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.A))
        advance(stage, 0.5)
        assert not stage.paused and stage._alert is None
    finally:
        close(stage)
