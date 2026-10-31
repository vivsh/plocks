"""Exercise the actual game's B-button, cloned bullets and impact cleanup."""

import runpy
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest

from plocks import GamepadButton, GamepadInput, Sprite, Stage, TileMap
from plocks._gamepads import _apply
from plocks._runtime import advance, close


@pytest.fixture
def game() -> Iterator[Stage]:
    values = runpy.run_path(
        str(Path(__file__).parents[1] / "src/plocks/_games/clone_blaster/main.py")
    )
    stage = cast(Stage, values["stage"])
    stage._state = "running"
    stage._last_wall = 0
    try:
        tick(stage, 60)
        yield stage
    finally:
        close(stage)


def state(stage: Stage) -> dict[str, object]:
    return dict[str, object](stage._updates[0][1].__globals__)


def tick(stage: Stage, count: int) -> None:
    for _ in range(count):
        advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)


def copies(stage: Stage) -> list[Sprite]:
    return [actor for actor in stage.objects if isinstance(actor, Sprite) and actor.is_clone]


def test_fire_remove_then_fire_again(game: Stage) -> None:
    """Each B press after impact can still clone the attached hidden template."""
    template = cast(Sprite, state(game)["bullet"])
    baseline = len(game._touches)
    for index in range(20):
        _apply(game.gamepads[0], GamepadInput(buttons=frozenset({GamepadButton.B})))
        tick(game, 1)
        assert len(copies(game)) == 1
        bullet_clone = copies(game)[0]
        _apply(game.gamepads[0], GamepadInput())
        tick(game, 80)
        assert bullet_clone._stage is None and not copies(game)
        assert state(game)["hits"] == index + 1
        assert template._stage is game and not template.visible and not template.is_clone
        assert len(game._touches) == baseline
    assert state(game)["shots"] == 20


def test_holding_b_continues_after_many_impacts(game: Stage) -> None:
    """Simulation-time repeat fires for 20 seconds without detaching the template."""
    _apply(game.gamepads[0], GamepadInput(buttons=frozenset({GamepadButton.B})))
    tick(game, 1200)
    _apply(game.gamepads[0], GamepadInput())
    tick(game, 100)
    assert cast(int, state(game)["shots"]) > 100
    assert state(game)["hits"] == state(game)["shots"]
    assert not copies(game)
    assert cast(Sprite, state(game)["bullet"])._stage is game
    assert not game._actions


def test_wall_and_offscreen_remove_only_their_bullet(game: Stage) -> None:
    template = cast(Sprite, state(game)["bullet"])
    for position, velocity in (((350, 0), (520, 0)), ((-390, 200), (-520, 0))):
        bullet_clone = template.clone()
        bullet_clone.visible = True
        bullet_clone.position = position
        bullet_clone.body.velocity = velocity
        tick(game, 10)
        assert bullet_clone._stage is None
        assert template._stage is game
    assert state(game)["hits"] == 0


def test_turning_left_keeps_hero_grounded_and_shots_go_left(game: Stage) -> None:
    """A centered physical anchor keeps the mirrored hero aligned with its collider."""
    hero = cast(Sprite, state(game)["hero"])
    bottom = hero.bounds.bottom
    _apply(game.gamepads[0], GamepadInput(left_stick=(-1, 0)))
    tick(game, 10)
    assert hero.direction == 270
    assert hero.bounds.bottom == pytest.approx(bottom, abs=0.3)
    assert hero.body.grounded
    _apply(game.gamepads[0], GamepadInput(buttons=frozenset({GamepadButton.B})))
    tick(game, 1)
    bullet_clone = copies(game)[0]
    assert bullet_clone.body.velocity == (-520, 0)
    _apply(game.gamepads[0], GamepadInput())
    tick(game, 100)
    assert bullet_clone._stage is None
    assert cast(Sprite, state(game)["bullet"])._stage is game

    _apply(game.gamepads[0], GamepadInput(left_stick=(-1, 0)))
    tick(game, 180)
    world = cast(TileMap, state(game)["world"])
    assert hero.bounds.left >= world.bounds.left + world.tile_size[0] - 0.3
    assert hero.body.grounded
