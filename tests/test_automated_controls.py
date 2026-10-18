"""Computer players reuse human control mechanics without network dependencies."""

from __future__ import annotations

import pytest

from plocks import (
    Event,
    GamepadButton,
    GamepadInput,
    GamepadPress,
    Key,
    Multiplayer,
    Stage,
    StageError,
)
from plocks._runtime import advance, close


def test_bot_controls_precede_gameplay_and_pause_with_simulation() -> None:
    """One driver sample is visible to callbacks/updates in that simulation step."""
    stage = Stage(gamepad_count=1)
    pad = stage.gamepads[0]
    calls: list[float] = []
    held: list[bool] = []
    presses: list[int] = []

    @stage.on_bot(gamepad=pad)
    def computer(event: Event[Stage, float]) -> GamepadInput:
        calls.append(event.data)
        return GamepadInput(buttons=frozenset({GamepadButton.A}), left_stick=(0.5, 0))

    @stage.on_button_down(GamepadButton.A, gamepad=pad)
    def pressed(event: Event[Stage, GamepadPress]) -> None:
        presses.append(1)

    @stage.on_update
    def update(event: Event[Stage, float]) -> None:
        held.append(pad.is_down(GamepadButton.A))

    stage._state = "running"
    try:
        advance(stage, 0)
        advance(stage, 1 / 60)
        advance(stage, 2 / 60)
        assert calls == [1 / 60] * 2 and held == [True, True] and presses == [1]
        assert pad.left_stick == (0.5, 0)
        stage._held_keys.add(Key.F)
        assert not pad.is_down(GamepadButton.B)
        stage.pause()
        advance(stage, 10)
        assert len(calls) == 2
    finally:
        close(stage)
    assert not stage._bots and not stage._held_keys


def test_bot_registration_is_exclusive_and_before_run() -> None:
    """A slot cannot secretly mix local, automated, and remote source ownership."""
    stage = Stage(gamepad_count=2)

    def driver(event: Event[Stage, float]) -> GamepadInput:
        return GamepadInput()

    stage.on_bot(gamepad=stage.gamepads[1])(driver)
    with pytest.raises(StageError, match="already"):
        stage.on_bot(gamepad=stage.gamepads[1])(driver)
    with pytest.raises(StageError, match="belonging"):
        stage.on_bot(gamepad=Stage().gamepads[0])(driver)
    with pytest.raises(StageError, match="both remote and automated"):
        stage.run(multiplayer=Multiplayer(slots=(1,)))
    assert stage._state == "new" and stage._target is None
    stage._state = "running"
    with pytest.raises(StageError, match="before run"):
        stage.on_bot(gamepad=stage.gamepads[0])(driver)
    close(stage)


def test_public_keyboard_gameplay_api_is_removed() -> None:
    """Keys configure mappings; gameplay uses buttons, sticks, or pointer APIs."""
    import plocks

    stage = Stage()
    assert not hasattr(plocks, "Keyboard") and not hasattr(plocks, "KeyDown")
    assert not hasattr(stage, "keyboard") and not hasattr(stage, "on_key_down")
    assert not hasattr(stage, "on_gamepad_button_down")
    assert stage.mouse.position == (0, 0)


def test_computer_opponent_uses_the_human_movement_and_attack_path() -> None:
    """An opponent approaches, attacks, and follows a moving human using only controls."""
    from pathlib import Path

    from plocks import Sprite

    image = Path(__file__).parents[1] / "src/plocks/_games/platformer/assets/hero.png"
    stage = Stage(gamepad_count=2)
    human, opponent = Sprite(image), Sprite(image, x=100)
    stage.add(human)
    stage.add(opponent)
    attacks: list[int] = []

    @stage.on_bot(gamepad=stage.gamepads[1])
    def decide(event: Event[Stage, float]) -> GamepadInput:
        distance = human.x - opponent.x
        steering = 0.0 if abs(distance) < 20 else (1.0 if distance > 0 else -1.0)
        buttons = frozenset({GamepadButton.A}) if abs(distance) < 30 else frozenset()
        return GamepadInput(buttons=buttons, left_stick=(steering, 0))

    @stage.on_button_down(GamepadButton.A)
    def attack(event: Event[Stage, GamepadPress]) -> None:
        attacks.append(event.data.gamepad.index)

    @stage.on_update
    def move(event: Event[Stage, float]) -> None:
        for actor, pad in zip((human, opponent), stage.gamepads):
            actor.x += pad.left_stick[0] * 80 * event.data

    stage._state = "running"
    try:
        advance(stage, 0)
        for tick in range(1, 121):
            advance(stage, tick / 60)
        assert human.x == 0 and 18 <= opponent.x <= 21 and attacks == [1]
        stage._held_keys.add(Key.D)
        for tick in range(121, 181):
            advance(stage, tick / 60)
        assert human.x > 70 and opponent.x > 50
    finally:
        close(stage)
