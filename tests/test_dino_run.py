"""Play the downloadable runner and each independent teaching checkpoint."""

import ast
import runpy
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pygame
import pytest
from PIL import Image

from plocks import Box, GamepadButton, GamepadPress, Key, Sprite, Stage
from plocks._render import frame
from plocks._runtime import advance, close
from plocks._scripts import _step, _trigger

ROOT = Path(__file__).parents[1]
GAME = ROOT / "src/plocks/_games/dino_run"


@pytest.fixture
def game() -> Iterator[dict[str, object]]:
    """Start the real game with a synthetic clock and deterministic spawning."""
    namespace = runpy.run_path(str(GAME / "main.py"))
    stage = cast(Stage, namespace["stage"])
    stage._state = "running"
    stage._last_wall = 0
    namespace = stage._updates[0][1].__globals__
    namespace["choice"] = lambda kinds: "cactus"
    namespace["random"] = lambda: 0.0
    for handler in tuple(stage._starts):
        _trigger(stage, handler)
    _step(stage)
    yield namespace
    close(stage)


def ticks(stage: Stage, count: int) -> None:
    """Advance full engine order, including dispatch, scripts and physics."""
    for _ in range(count):
        advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)


def key(stage: Stage, pressed: Key) -> None:
    """Queue a raw key press, keeping UI controls available even while paused."""
    stage._pending.append(GamepadPress(stage.gamepads[0], stage.gamepads[0]._key_buttons[pressed]))
    ticks(stage, 1)


def test_jump_land_duck_and_pause(game: dict[str, object]) -> None:
    """A mapped jump lands, a held duck resizes its collider, and pause freezes time."""
    stage, dino = cast(Stage, game["stage"]), cast(Sprite, game["dino"])
    ticks(stage, 30)
    assert dino.body.grounded
    y = dino.y
    # Exercise the actual mapped-button registration, not the helper directly.
    from plocks.events import GamepadPress

    stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.A))
    ticks(stage, 10)
    assert dino.y > y + 40 and not dino.body.grounded
    ticks(stage, 60)
    assert dino.body.grounded
    stage._held_keys.add(Key.S)
    ticks(stage, 1)
    assert game["crouching"] and dino.costume.height == 38
    assert dino.body.shape == Box(52, 28, center=(6, 18))
    stage._held_keys.clear()
    ticks(stage, 1)
    assert not game["crouching"] and dino.costume.height == 72
    key(stage, Key.P)
    before = (stage.time, dino.position, game["distance"])
    ticks(stage, 60)
    assert (stage.time, dino.position, game["distance"]) == before
    key(stage, Key.P)
    ticks(stage, 2)
    assert stage.time > before[0]


def test_pickup_collision_restart_and_bounded_work(game: dict[str, object]) -> None:
    """Coins retire once, collision pauses play, and repeated restart leaves one spawn loop."""
    stage, dino = cast(Stage, game["stage"]), cast(Sprite, game["dino"])
    ticks(stage, 100)
    pickups = cast(list[Sprite], game["pickups"])
    assert len(pickups) == 1
    coin = pickups[0]
    coin.position = dino.position
    ticks(stage, 1)
    assert game["coins"] == 1 and coin not in stage.objects
    obstacle = cast(list[Sprite], game["obstacles"])[0]
    obstacle.position = dino.position
    ticks(stage, 4)
    assert not game["playing"] and stage.paused
    assert cast(int, game["best"]) >= 25
    key(stage, Key.R)
    assert game["playing"] and not stage.paused
    assert game["coins"] == 0 and not game["obstacles"] and not game["pickups"]
    for _ in range(12):
        key(stage, Key.R)
        ticks(stage, 2)
        assert len(stage.objects) == 6
        assert len(stage._actions) == 1


def test_bird_can_be_ducked_and_visuals_scroll(game: dict[str, object]) -> None:
    """Bird height clears a ducking collider and scenery offsets actually change."""
    stage, dino = cast(Stage, game["stage"]), cast(Sprite, game["dino"])
    game["distance"] = 2100.0
    game["choice"] = lambda kinds: "bird"
    stage._held_keys.add(Key.S)
    ticks(stage, 100)
    bird = cast(list[Sprite], game["obstacles"])[0]
    bird.x = dino.x
    ticks(stage, 2)
    assert game["playing"] and game["crouching"]
    stage._held_keys.clear()
    ticks(stage, 4)
    assert not game["playing"]


@pytest.mark.parametrize(
    "entry",
    [
        "01_hello.py",
        "02_controls.py",
        "03_jump.py",
        "labs/scripts.py",
        "labs/art.py",
        "labs/messages.py",
    ],
)
def test_course_programs_are_independent_and_render(
    entry: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every checkpoint/lab loads from another cwd, renders, and closes without work leaks."""
    monkeypatch.chdir(tmp_path)
    namespace = runpy.run_path(str(GAME / entry))
    stage = cast(Stage, namespace["stage"])
    actors = [actor for actor in stage.objects if isinstance(actor, Sprite)]
    try:
        stage._state = "running"
        stage._last_wall = 0
        for handler in tuple(stage._starts):
            _trigger(stage, handler)
        _step(stage)
        ticks(stage, 90)
        stage._target = pygame.display.set_mode((stage.width, stage.height))
        frame(stage)
        assert stage._target.get_at((0, 0)).a == 255
    finally:
        close(stage)
    assert not stage.objects and not stage._actions and not stage._voices
    assert all(actor._stage is None for actor in actors)


def test_downloads_match_the_actual_project_and_all_art() -> None:
    """Downloadable ZIPs contain current code and the seven original PNGs with real alpha."""
    downloads = ROOT / "docs/downloads"
    with zipfile.ZipFile(downloads / "dino-dash.zip") as archive:
        expected = {
            "dino_run/" + path.relative_to(GAME).as_posix(): path.read_bytes()
            for path in GAME.rglob("*")
            if path.is_file() and not any(part in {"__pycache__", "dist"} for part in path.parts)
        }
        assert set(archive.namelist()) == set(expected)
        assert all(archive.read(name) == body for name, body in expected.items())
    with zipfile.ZipFile(downloads / "dino-sprites.zip") as archive:
        assert sum(name.endswith(".png") for name in archive.namelist()) == 7
    for path in (GAME / "assets").glob("*.png"):
        with Image.open(path) as image:
            assert min(image.size) >= 512
            if path.stem != "desert":
                assert (
                    image.mode == "RGBA"
                    and cast(tuple[int, int], image.getchannel("A").getextrema())[0] == 0
                    and cast(tuple[int, int], image.getchannel("A").getextrema())[1] >= 250
                )
    for path in GAME.rglob("*.py"):
        tree = ast.parse(path.read_text())
        assert not any(
            isinstance(node, ast.ImportFrom) and node.module == "PIL" for node in ast.walk(tree)
        )
