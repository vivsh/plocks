"""Play the standalone action example through deterministic input and simulation."""

import runpy
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from plocks import Event, Key, Sprite, Stage
from plocks._runtime import close, dispatch
from plocks._scripts import _deliver, _sample, _step, _trigger


@pytest.fixture
def game() -> Iterator[Stage]:
    """Load the real example, intercept its window, then start its script bindings."""
    stages: list[Stage] = []

    def capture(stage: Stage) -> None:
        stages.append(stage)

    filename = Path(__file__).parents[1] / "examples/jungle_run/main.py"
    with patch.object(Stage, "run", capture):
        runpy.run_path(str(filename), run_name="__main__")
    stage = stages[0]
    stage._state = "running"
    for handler in tuple(stage._starts):
        _trigger(stage, handler)
    _step(stage)
    yield stage
    close(stage)


def state(stage: Stage) -> dict[str, object]:
    """Inspect authored game values without adding test hooks to the example."""
    return dict[str, object](stage._updates[0][1].__globals__)


def advance(stage: Stage, ticks: int) -> None:
    """Use the engine's fixed-step order, including authored synchronous physics."""
    for _ in range(ticks):
        stage._tick += 1
        _sample(stage)
        _deliver(stage)
        dispatch(stage)
        _step(stage)
        for actor, update in tuple(stage._updates):
            occurrence = Event(stage, stage if actor is None else actor, 1 / stage.tick_rate)
            cast(Callable[[object], None], update)(occurrence)


def press(stage: Stage, key: Key) -> None:
    """Send a new key press and hold it for subsequent simulation ticks."""
    stage.keyboard._down.add(key)
    stage._pending.append(key)


def test_running_jump_and_airborne_shooting(game: Stage) -> None:
    """The player can move and shoot during a jump without gaining a double jump."""
    hero = cast(Sprite, state(game)["hero"])
    press(game, Key.RIGHT)
    press(game, Key.SPACE)
    press(game, Key.X)
    advance(game, 15)
    assert hero.x > -300 and hero.y > -150
    assert state(game)["shots"]
    press(game, Key.SPACE)
    advance(game, 12)
    assert hero.y < -5  # A second Space cannot restart the ascent.
    game.keyboard._down.clear()
    advance(game, 50)
    assert hero.y == -150


def test_platform_landing_and_walking_off(game: Stage) -> None:
    """A jump passes through a ledge, lands on top and falls when walking off."""
    hero = cast(Sprite, state(game)["hero"])
    hero.x = 150
    press(game, Key.SPACE)
    advance(game, 55)
    assert hero.y == -86
    assert state(game)["vertical_speed"] == 0
    press(game, Key.LEFT)
    advance(game, 85)
    assert hero.x < 0 and hero.y == -150


def test_projectiles_defeat_sentry_and_restart(game: Stage) -> None:
    """Held fire destroys a robot; restart resets enemies, health and projectiles."""
    hero = cast(Sprite, state(game)["hero"])
    hero.x = -100
    press(game, Key.X)
    advance(game, 65)
    assert cast(int, state(game)["defeated"]) >= 1
    assert len(cast(list[Sprite], state(game)["enemies"])) < 6
    game.keyboard._down.clear()
    press(game, Key.R)
    advance(game, 1)
    assert len(cast(list[Sprite], state(game)["enemies"])) == 6
    assert state(game)["health"] == 3 and state(game)["defeated"] == 0
    assert not state(game)["shots"]
    assert hero.position == (-300, -150)


def test_contact_damage_has_grace_period(game: Stage) -> None:
    """Remaining in contact cannot consume all health in consecutive frames."""
    hero = cast(Sprite, state(game)["hero"])
    enemies = cast(list[Sprite], state(game)["enemies"])
    hero.position = enemies[0].position
    advance(game, 1)
    assert state(game)["health"] == 2
    advance(game, 20)
    assert state(game)["health"] == 2


def test_repeated_restart_and_close_retire_scripts(game: Stage) -> None:
    """Restart leaves one patrol/fire tree per robot and closure retires everything."""
    for _ in range(4):
        press(game, Key.R)
        advance(game, 1)
        assert len(game._actions) == 6
    actors = [obj for obj in game.objects if isinstance(obj, Sprite)]
    close(game)
    assert not game._actions and not game.objects
    assert all(actor._stage is None for actor in actors)
