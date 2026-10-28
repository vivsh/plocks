"""Logical releases and per-body slowdown through the real stage driver."""

import pygame
import pytest

from plocks import Event, GamepadButton, GamepadRelease, Image, Sprite, Stage


def test_release_and_drag_through_running_stage() -> None:
    """Releasing mapped Space fires once while the dynamic actor coasts to a stop."""
    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    hero = Sprite(Image.rectangle(12, 12, color="orange"))
    stage.add(hero)
    hero.body.drag = (600, 0)
    hero.body.velocity = (240, 0)
    released: list[GamepadRelease] = []
    stopped: list[tuple[float, float]] = []

    @hero.on_button_up(GamepadButton.A, gamepad=stage.gamepads[0])
    def release(event: Event[Sprite, GamepadRelease]) -> None:
        assert event.source is stage and event.target is hero
        assert not event.data.gamepad.is_down(event.data.button)
        released.append(event.data)

    @stage.on_start
    def start(event: Event[Stage, None]) -> None:
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))

    @stage.on_update
    def update(event: Event[Stage, float]) -> None:
        tick = round(stage.time * 60)
        if tick == 5:
            pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))
        if tick >= 32:
            stopped.append((hero.x, hero.body.velocity[0]))
            stage.stop()

    stage.run()
    assert len(released) == 1 and released[0].button is GamepadButton.A
    assert stopped[0][1] == 0 and stopped[0][0] == pytest.approx(48, abs=3)
    assert not stage.objects


def test_multiple_keys_and_clones_share_logical_release() -> None:
    """A logical release waits for every mapped key; clones inherit independent callbacks and drag."""
    from plocks import Key
    from plocks._runtime import _key, close, dispatch

    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    hero = Sprite(Image.rectangle(10, 10, color="red"))
    stage.add(hero)
    hero.body.drag = (30, 10)
    pad = stage.gamepads[0]
    pad.map_key(Key.ENTER, GamepadButton.A)
    seen: list[Sprite] = []

    @hero.on_button_up(GamepadButton.A, gamepad=pad)
    def released(event: Event[Sprite, GamepadRelease]) -> None:
        seen.append(event.target)

    stage._state = "running"
    clone = hero.clone()
    assert clone.body.drag == (30, 10)
    clone.body.drag = (5, 0)
    assert hero.body.drag == (30, 10)
    try:
        for kind, code in (
            (pygame.KEYDOWN, pygame.K_SPACE),
            (pygame.KEYDOWN, pygame.K_RETURN),
            (pygame.KEYUP, pygame.K_SPACE),
        ):
            _key(stage, pygame.event.Event(kind, key=code))
            dispatch(stage)
        assert seen == [] and pad.is_down(GamepadButton.A)
        _key(stage, pygame.event.Event(pygame.KEYUP, key=pygame.K_RETURN))
        dispatch(stage)
        assert seen == [hero, clone]
        stage.remove(clone)
        assert all(
            handler.actor is not clone
            for handlers in stage._gamepad_up_handlers.values()
            for handler in handlers
        )
    finally:
        close(stage)
    assert not stage._gamepad_up_handlers


def test_drag_validation_independent_axes_and_body_lifetime() -> None:
    """Drag never reverses velocity, preserves unconfigured y and resets after reattachment."""
    from plocks import PhysicsError
    from plocks._runtime import advance, close

    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    hero = Sprite(Image.rectangle(10, 10, color="red"))
    stage.add(hero)
    body = hero.body
    assert body.drag == (0, 0)
    body.drag = (120, 0)
    body.velocity = (-10, 40)
    for value in ((-1.0, 0.0), (float("nan"), 0.0), (0.0, float("inf"))):
        with pytest.raises(ValueError):
            body.drag = value
        assert body.drag == (120, 0)
    stage._state, stage._last_wall = "running", 0
    try:
        for _ in range(10):
            advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)
        assert body.velocity[0] == 0 and body.velocity[1] == pytest.approx(40)
        stage.remove(hero)
        with pytest.raises(PhysicsError):
            _ = body.drag
        stage.add(hero)
        assert hero.body.drag == (0, 0)
    finally:
        close(stage)


def test_stage_and_puppet_receive_the_released_player() -> None:
    """Stage and Puppet decorators receive the correct second-player release payload."""
    from plocks import Key, Puppet
    from plocks._runtime import _key, close, dispatch

    stage = Stage(gamepad_count=2)
    puppet = Puppet.stick_figure()
    stage.add(puppet)
    pad = stage.gamepads[1]
    pad.map_key(Key.J, GamepadButton.X)
    seen: list[tuple[object, GamepadRelease]] = []

    @stage.on_button_up(GamepadButton.X)
    def on_stage(event: Event[Stage, GamepadRelease]) -> None:
        seen.append((event.target, event.data))

    @puppet.on_button_up(GamepadButton.X, gamepad=pad)
    def on_puppet(event: Event[Puppet, GamepadRelease]) -> None:
        seen.append((event.target, event.data))

    stage._state = "running"
    try:
        for kind in (pygame.KEYDOWN, pygame.KEYUP):
            _key(stage, pygame.event.Event(kind, key=pygame.K_j))
            dispatch(stage)
        assert [target for target, _ in seen] == [stage, puppet]
        assert all(data.gamepad is pad and data.button is GamepadButton.X for _, data in seen)
    finally:
        close(stage)


def test_release_stops_turbo_and_starts_script() -> None:
    """Release stops repeat and can start a reusable actor script once."""
    from plocks import GamepadPress
    from plocks._runtime import _key, advance, close, dispatch

    stage = Stage()
    hero = Sprite(Image.rectangle(8, 8, color="blue"))
    stage.add(hero)
    pad = stage.gamepads[0]
    presses: list[int] = []

    @hero.on_button_down(GamepadButton.A, gamepad=pad, repeat=0.05)
    def pressed(event: Event[Sprite, GamepadPress]) -> None:
        presses.append(1)

    hero.on_button_up(GamepadButton.A, hero.sequence().move(10), gamepad=pad)
    stage._state, stage._last_wall = "running", 0
    try:
        _key(stage, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        dispatch(stage)
        for _ in range(12):
            advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)
        assert len(presses) >= 3
        _key(stage, pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))
        dispatch(stage)
        before = len(presses)
        for _ in range(12):
            advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)
        assert len(presses) == before and hero.x == pytest.approx(10)
    finally:
        close(stage)
