"""Graphic effect actions share the simulation clock and existing ownership rules."""

from collections.abc import Iterator
from pathlib import Path

import pygame
import pytest

from plocks import Effect, Image, Sprite, Stage
from plocks._effects import _apply
from plocks._operations import _EffectRun
from plocks._runtime import close
from plocks._scripts import _sample, _step
from plocks.effects import _value


@pytest.fixture
def stage() -> Iterator[Stage]:
    owner = Stage()
    owner._state = "running"
    yield owner
    close(owner)


def tick(stage: Stage, count: int = 1) -> None:
    for _ in range(count):
        if stage.running and not stage.paused:
            _step(stage)
            stage._tick += 1
            _sample(stage)


def actor(stage: Stage) -> Sprite:
    result = Sprite(Image.rectangle(10, 10, color="red"))
    stage.add(result)
    return result


def test_fade_while_another_actor_moves(stage: Stage) -> None:
    hero, friend = actor(stage), actor(stage)
    fade = hero.animate_effect(Effect.GHOST, to=100, seconds=1)
    movement = friend.glide_by(x=120, seconds=1)
    assert hero._effects == {} and friend.x == 0
    tick(stage, 30)
    assert isinstance(hero._effects[Effect.GHOST], _EffectRun)
    assert _value(hero, Effect.GHOST) == pytest.approx(50)
    assert friend.x == pytest.approx(60)
    faded = _apply(hero.image._pixels, hero)
    assert faded.get_at((5, 5)).a == pytest.approx(128, abs=1)
    assert hero.image._pixels.get_at((5, 5)).a == 255
    tick(stage, 31)
    assert fade.done and movement.done and friend.x == 120
    assert hero._effects[Effect.GHOST] == 100
    assert _apply(hero.image._pixels, hero).get_at((5, 5)).a == 0


def test_pause_and_cancellation_freeze_amount(stage: Stage) -> None:
    hero = actor(stage)
    fade = hero.animate_effect(Effect.GHOST, to=100, seconds=1)
    tick(stage, 20)
    before = _value(hero, Effect.GHOST)
    stage.pause()
    tick(stage, 20)
    assert _value(hero, Effect.GHOST) == before
    stage.resume()
    fade.cancel()
    assert hero._effects[Effect.GHOST] == before and fade.cancelled
    tick(stage, 40)
    assert _value(hero, Effect.GHOST) == before


def test_replacement_cancels_whole_root_and_clear_ends_all_writers(stage: Stage) -> None:
    hero = actor(stage)
    root = hero.act(hero.sequence().animate_effect(Effect.GHOST, to=100, seconds=1).move(50))
    other = hero.animate_effect(Effect.BRIGHTNESS, to=80, seconds=2)
    tick(stage, 20)
    replacement = hero.set_effect(Effect.GHOST, 10)
    tick(stage)
    assert root.cancelled and replacement.done and not other.done
    assert hero.x == 0 and _value(hero, Effect.GHOST) == 10
    hero.clear_effects()
    tick(stage)
    assert other.cancelled and hero._effects == {}


def test_after_captures_origin_on_execution(stage: Stage) -> None:
    hero = actor(stage)
    wait = hero.wait(0.2)
    fade = hero.animate_effect(Effect.GHOST, to=100, seconds=0.5, after=wait)
    hero.set_effect(Effect.GHOST, 30)
    tick(stage, 12)
    assert _value(hero, Effect.GHOST) == 30
    tick(stage, 16)
    assert _value(hero, Effect.GHOST) == pytest.approx(30 + 70 * (0.5 + 1 / 30), abs=1e-7)
    tick(stage, 20)
    assert fade.done and _value(hero, Effect.GHOST) == 100


def test_first_path_render_uses_effect_pixels(stage: Stage) -> None:
    from plocks._render import frame

    hero = actor(stage)
    hero.set_effect(Effect.GHOST, 50)
    tick(stage)
    stage.background = "black"
    pygame.display.init()
    stage._target = pygame.display.set_mode((stage.width, stage.height))
    frame(stage)
    pixel = stage._target.get_at((stage.width // 2, stage.height // 2))
    assert pixel.r == pytest.approx(128, abs=1) and pixel.g == pixel.b == 0


@pytest.mark.parametrize("effect", list(Effect))
def test_every_effect_animates_and_retains_the_static_equivalent(
    stage: Stage, effect: Effect
) -> None:
    hero = actor(stage)
    action = hero.animate_effect(effect, to=60, seconds=0.1)
    tick(stage, 7)
    assert action.done and hero._effects[effect] == 60
    first = pygame.image.tobytes(_apply(hero.image._pixels, hero), "RGBA")
    hero.set_effect(effect, 60)
    tick(stage)
    assert pygame.image.tobytes(_apply(hero.image._pixels, hero), "RGBA") == first


def test_zero_duration_yields_and_repeat_keeps_exact_fractional_deadlines(stage: Stage) -> None:
    hero = actor(stage)
    zero = hero.act(hero.sequence().animate_effect(Effect.GHOST, to=60, seconds=0).clear_effects())
    tick(stage)
    assert not zero.done and _value(hero, Effect.GHOST) == 60
    tick(stage)
    assert zero.done and hero._effects == {}
    from plocks.actions import _Completion

    repeated = hero.act(
        hero.repeat(3)
        .animate_effect(Effect.GHOST, to=100, seconds=0.025)
        .animate_effect(Effect.GHOST, to=0, seconds=0.025)
    )
    started = stage.time
    tick(stage, 10)
    assert repeated.done and _value(hero, Effect.GHOST) == 0
    assert isinstance(repeated._state, _Completion)
    assert repeated._state.at == pytest.approx(started + 0.15)


def test_easing_and_color_cycle(stage: Stage) -> None:
    from plocks import Ease

    hero = actor(stage)
    action = hero.animate_effect(Effect.GHOST, to=100, seconds=1, easing=Ease.IN)
    tick(stage, 30)
    assert _value(hero, Effect.GHOST) == pytest.approx(25)
    action.cancel()
    hero.animate_effect(Effect.COLOR, to=200, seconds=1)
    tick(stage, 30)
    assert _value(hero, Effect.COLOR) == pytest.approx(100)
    tick(stage, 31)
    assert _value(hero, Effect.COLOR) == 0


def test_change_reads_at_execution_and_validates_overflow_before_cancelling(stage: Stage) -> None:
    hero = actor(stage)
    hero.set_effect(Effect.BRIGHTNESS, 20)
    first = hero.wait(0.1)
    last = hero.change_effect(Effect.BRIGHTNESS, by=30, after=first)
    tick(stage, 8)
    assert last.done and _value(hero, Effect.BRIGHTNESS) == 50
    hero.set_effect(Effect.WHIRL, 1e308)
    tick(stage)
    writer = hero.animate_effect(Effect.WHIRL, to=1e308, seconds=1)
    tick(stage)
    hero.change_effect(Effect.WHIRL, by=1e308)
    with pytest.raises(ValueError, match="effect amount"):
        tick(stage)
    assert not writer.done and _value(hero, Effect.WHIRL) == 1e308


@pytest.mark.parametrize("clear", [False, True])
def test_during_rejects_competing_sibling_writers(stage: Stage, clear: bool) -> None:
    from plocks import StageError

    hero = actor(stage)
    foreground = hero.sequence().animate_effect(Effect.GHOST, to=100, seconds=1)
    background = (
        hero.sequence().clear_effects() if clear else hero.sequence().set_effect(Effect.GHOST, 20)
    )
    hero.act(hero.sequence().during(foreground, meanwhile=background))
    with pytest.raises(StageError, match="same property"):
        tick(stage)
    assert all(not isinstance(value, _EffectRun) for value in hero._effects.values())


def test_during_distinct_effects_compose_and_cancel_background(stage: Stage) -> None:
    hero = actor(stage)
    main = hero.sequence().animate_effect(Effect.GHOST, to=100, seconds=0.2)
    background = hero.sequence().animate_effect(Effect.BRIGHTNESS, to=100, seconds=1)
    action = hero.act(hero.sequence().during(main, meanwhile=background))
    tick(stage, 14)
    assert action.done and _value(hero, Effect.GHOST) == 100
    assert _value(hero, Effect.BRIGHTNESS) == pytest.approx(20)
    assert all(not isinstance(value, _EffectRun) for value in hero._effects.values())


def test_removal_readd_clone_snapshot_and_closure_freeze(stage: Stage) -> None:
    hero = actor(stage)
    hero.animate_effect(Effect.GHOST, to=100, seconds=1)
    tick(stage, 30)
    copy = hero.clone()
    assert copy._effects == {Effect.GHOST: pytest.approx(50)}
    assert copy._effects is not hero._effects
    copy.set_effect(Effect.GHOST, 10)
    tick(stage)
    assert _value(copy, Effect.GHOST) == 10 and _value(hero, Effect.GHOST) > 50
    hero.remove()
    frozen = _value(hero, Effect.GHOST)
    assert not isinstance(hero._effects[Effect.GHOST], _EffectRun)
    stage.add(hero)
    tick(stage, 20)
    assert _value(hero, Effect.GHOST) == frozen
    hero.animate_effect(Effect.GHOST, to=100, seconds=1)
    tick(stage, 10)
    before = _value(hero, Effect.GHOST)
    close(stage)
    assert hero._effects[Effect.GHOST] == before and hero._stage is None
    assert not stage._actions


def test_effects_survive_image_changes_and_do_not_change_physics(stage: Stage) -> None:
    from plocks import BodyType

    physical = Stage(physics=True)
    hero = Sprite(Image.rectangle(20, 40), body_type=BodyType.KINEMATIC)
    physical.add(hero)
    physical._state = "running"
    try:
        shape, bounds = hero.body.shape, hero.bounds
        hero.animate_effect(Effect.GHOST, to=100, seconds=1)
        tick(physical, 20)
        assert hero.body.shape == shape and hero.bounds == bounds
        hero.image = Image.rectangle(20, 40, color="blue")
        tick(physical, 20)
        assert _value(hero, Effect.GHOST) == pytest.approx(100 * 2 / 3)
        assert hero.body.shape == shape and hero.bounds == bounds
    finally:
        close(physical)


@pytest.mark.parametrize("amount", [float("inf"), float("-inf"), float("nan")])
def test_invalid_values_are_rejected_before_scheduling(stage: Stage, amount: float) -> None:
    hero = actor(stage)
    existing = hero.animate_effect(Effect.GHOST, to=100, seconds=1)
    tick(stage)
    with pytest.raises(ValueError):
        hero.set_effect(Effect.GHOST, amount)
    with pytest.raises(ValueError):
        hero.change_effect(Effect.GHOST, amount)
    with pytest.raises(ValueError):
        hero.animate_effect(Effect.GHOST, to=amount, seconds=1)
    with pytest.raises(ValueError):
        hero.animate_effect(Effect.GHOST, to=30, seconds=amount)
    with pytest.raises(ValueError):
        hero.animate_effect(Effect.GHOST, to=30, seconds=-1)
    assert not existing.done


def test_runtime_validation_detached_and_after_contract(stage: Stage) -> None:
    from plocks import Ease, StageError

    hero = actor(stage)
    invalid_effect: object = "ghost"
    invalid_easing: object = "linear"
    from typing import cast

    with pytest.raises(TypeError, match="Effect"):
        hero.set_effect(cast(Effect, invalid_effect), 10)
    with pytest.raises(TypeError):
        hero.set_effect(Effect.GHOST, True)
    with pytest.raises(TypeError, match="Ease"):
        hero.animate_effect(Effect.GHOST, to=10, seconds=1, easing=cast(Ease, invalid_easing))
    hero.remove()
    with pytest.raises(StageError):
        hero.set_effect(Effect.GHOST, 20)
    assert hero._effects == {}


def test_approved_effect_record_fields_and_actor_ownership() -> None:
    from dataclasses import fields

    import plocks
    from plocks import Puppet
    from plocks._commands import _AnimateEffect, _ChangeEffect, _ClearEffects, _SetEffect

    assert "Effect" in plocks.__all__ and len(Effect) == 7
    assert tuple(field.name for field in fields(_EffectRun)) == (
        "actor",
        "effect",
        "start",
        "end",
        "started",
        "seconds",
        "easing",
    )
    assert tuple(field.name for field in fields(_AnimateEffect)) == (
        "effect",
        "to",
        "seconds",
        "easing",
    )
    assert tuple(field.name for field in fields(_SetEffect)) == ("effect", "value")
    assert tuple(field.name for field in fields(_ChangeEffect)) == ("effect", "by")
    assert not fields(_ClearEffects)
    assert "_effects" in Sprite.__slots__ and "_effects" in Puppet.__slots__


def test_complete_download_activity(tmp_path: Path) -> None:
    import runpy
    import shutil
    from typing import cast

    from plocks import GamepadButton, GamepadPress
    from plocks._runtime import dispatch
    from plocks._scripts import _trigger

    root = Path(__file__).parents[1]
    source = root / "docs/activities/effects.py"
    shutil.copy2(source, tmp_path / "effects.py")
    shutil.copytree(root / "src/plocks/_games/dino_run/assets", tmp_path / "assets")
    values = runpy.run_path(str(tmp_path / "effects.py"))
    stage = cast(Stage, values["stage"])
    hero, bird = cast(Sprite, values["hero"]), cast(Sprite, values["bird"])
    stage._state = "running"
    try:
        for handler in tuple(stage._starts):
            _trigger(stage, handler)
        tick(stage, 30)
        assert hero.x > -100 and _value(bird, Effect.COLOR) > 0
        stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.B))
        dispatch(stage)
        tick(stage, 21)
        assert 45 < _value(hero, Effect.GHOST) < 55
        stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.Y))
        dispatch(stage)
        tick(stage)
        assert hero._effects == {} and _value(bird, Effect.COLOR) > 0
    finally:
        close(stage)
