"""Play the real railgun example: ray damage, beam rendering and physical bumps."""

import runpy
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pygame
import pytest

from plocks import BodyType, GamepadButton, GamepadInput, Label, Sprite, Stage, TileMap
from plocks._gamepads import _apply
from plocks._render import frame
from plocks._runtime import advance, close


def tick(stage: Stage, count: int = 1) -> None:
    for _ in range(count):
        advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)


@pytest.fixture
def game() -> Iterator[Stage]:
    values = runpy.run_path(str(Path(__file__).parents[1] / "src/plocks/_games/railgun/main.py"))
    stage = cast(Stage, values["stage"])
    stage._state = "running"
    stage._last_wall = 0
    tick(stage, 60)
    yield stage
    close(stage)


def state(stage: Stage) -> dict[str, object]:
    return dict[str, object](stage._updates[0][1].__globals__)


def press(stage: Stage, button: GamepadButton) -> None:
    _apply(stage.gamepads[0], GamepadInput(buttons=frozenset({button})))
    tick(stage)
    _apply(stage.gamepads[0], GamepadInput())
    tick(stage)


def beams(stage: Stage) -> list[Sprite]:
    return [obj for obj in stage.objects if isinstance(obj, Sprite) and obj.layer == 100]


def test_cover_stops_ray_then_next_shot_hits_robot(game: Stage) -> None:
    values = state(game)
    cover = cast(TileMap, values["cover"])
    targets = cast(list[Sprite], values["targets"])
    press(game, GamepadButton.B)
    assert cover.get_tile(row=0, column=0) is None
    assert targets[0] in game.objects and state(game)["hits"] == 0
    assert len(beams(game)) == 3
    assert all(beam.bounds.right == pytest.approx(-64) for beam in beams(game))
    press(game, GamepadButton.B)
    assert targets[0] not in game.objects and state(game)["hits"] == 1
    assert all(beam.bounds.right == pytest.approx(36) for beam in beams(game)[-3:])


def test_all_targets_and_reset_work_through_input(game: Stage) -> None:
    for _ in range(6):
        press(game, GamepadButton.B)
    assert state(game)["shots"] == 6 and state(game)["hits"] == 3
    targets = cast(list[Sprite], state(game)["targets"])
    assert all(target not in game.objects for target in targets)
    press(game, GamepadButton.SELECT)
    assert state(game)["shots"] == state(game)["hits"] == 0
    assert all(target in game.objects for target in targets)
    cover = cast(TileMap, state(game)["cover"])
    assert all(cover.get_tile(row=0, column=col) == "#" for col in (0, 7, 14))


def test_left_facing_beam_anchor_and_target(game: Stage) -> None:
    hero = cast(Sprite, state(game)["hero"])
    targets = cast(list[Sprite], state(game)["targets"])
    hero.position = (780, -122)
    hero.direction = 270
    press(game, GamepadButton.B)
    assert targets[-1] not in game.objects
    assert all(beam.direction == 270 for beam in beams(game))
    assert all(beam.bounds.left == pytest.approx(624) for beam in beams(game))
    assert all(beam.bounds.right == pytest.approx(754) for beam in beams(game))


def test_beam_layers_pixels_pause_and_timed_expiry(game: Stage) -> None:
    press(game, GamepadButton.B)
    visible = beams(game)
    assert [beam.image.height for beam in visible] == [12, 4, 2]
    assert all(beam.body_type is BodyType.NONE and beam.image.anchor[0] == 0 for beam in visible)
    pygame.display.init()
    game._target = pygame.display.set_mode((game.width, game.height))
    frame(game)
    x = (visible[0].x + visible[0].bounds.right) / 2
    sx, sy = game.to_screen((x, visible[0].y))
    assert game._target.get_at((round(sx), round(sy)))[:3] == (255, 255, 255)
    sx, sy = game.to_screen((x, visible[0].y + 4))
    assert game._target.get_at((round(sx), round(sy)))[:3] == (20, 90, 171)
    game.pause()
    tick(game, 100)
    assert beams(game) == visible
    game.resume()
    tick(game, 20)
    assert not beams(game)


def test_real_hero_wall_hit_does_not_apply_ray_damage(game: Stage) -> None:
    hero = cast(Sprite, state(game)["hero"])
    hero.position = (-84, -122)
    hero.body.velocity = (0, 0)
    tick(game, 3)
    status = cast(Label, state(game)["status"])
    assert status.text.startswith("Wall contact!")
    assert state(game)["shots"] == state(game)["hits"] == 0
