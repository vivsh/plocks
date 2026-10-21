"""Play the downloadable runner and each independent teaching checkpoint."""

import ast
import runpy
import zipfile
from collections.abc import Iterator
from itertools import pairwise
from pathlib import Path
from typing import cast

import pygame
import pytest
from PIL import Image as PillowImage

from plocks import BodyType, Box, GamepadButton, GamepadPress, Key, Sprite, Stage, TileMap
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
    assert game["crouching"] and dino.image.height == 38
    assert dino.body.shape == Box(52, 28, center=(6, 18))
    stage._held_keys.clear()
    ticks(stage, 1)
    assert not game["crouching"] and dino.image.height == 72
    key(stage, Key.P)
    before = (stage.time, dino.position, stage.camera)
    ticks(stage, 60)
    assert (stage.time, dino.position, stage.camera) == before
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
        assert len(stage.objects) == 7
        assert len(stage._actions) == 1


def test_bird_can_be_ducked_and_visuals_scroll(game: dict[str, object]) -> None:
    """A fixed bird clears the ducking collider while the camera follows forward motion."""
    stage, dino = cast(Stage, game["stage"]), cast(Sprite, game["dino"])
    dino.x = 1840
    stage.camera = (2100, 0)
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
        with PillowImage.open(path) as image:
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


@pytest.mark.parametrize("control", ("button", "dpad", "stick"))
def test_each_controller_duck_input_is_supported(game: dict[str, object], control: str) -> None:
    """Shorter held-input code preserves controller B, d-pad Down and downward analog stick."""
    from plocks import GamepadInput
    from plocks._gamepads import _apply

    stage = cast(Stage, game["stage"])
    ticks(stage, 30)
    if control == "stick":
        sample = GamepadInput(left_stick=(0, -1))
    else:
        button = GamepadButton.B if control == "button" else GamepadButton.DOWN
        sample = GamepadInput(buttons=frozenset({button}))
    _apply(stage.gamepads[0], sample)
    ticks(stage, 1)
    assert game["crouching"]
    _apply(stage.gamepads[0], GamepadInput())
    ticks(stage, 1)
    assert not game["crouching"]


def test_camera_follows_runner_past_fixed_obstacles(game: dict[str, object]) -> None:
    """World objects stay fixed while the camera keeps the moving dinosaur at screen x=140."""
    stage, dino = cast(Stage, game["stage"]), cast(Sprite, game["dino"])
    ticks(stage, 100)
    obstacle = cast(list[Sprite], game["obstacles"])[0]
    coin = cast(list[Sprite], game["pickups"])[0]
    section = cast(list[TileMap], game["ground"])[0]
    positions = (obstacle.position, coin.position, (section.x, section.y))
    old_x, old_camera = dino.x, stage.camera[0]
    screen_x = stage.to_screen(obstacle.position)[0]
    ticks(stage, 10)
    assert obstacle.body_type is BodyType.STATIC
    assert obstacle.body.velocity == (0, 0)
    assert (obstacle.position, coin.position, (section.x, section.y)) == positions
    assert dino.x > old_x and stage.camera[0] > old_camera
    assert stage.to_screen(obstacle.position)[0] < screen_x
    assert stage.to_screen(dino.position)[0] == pytest.approx(140)
    assert stage.camera[1] == 0
    stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.A))
    ticks(stage, 10)
    assert not dino.body.grounded and stage.camera[1] == 0


def test_endless_floor_sections_stay_fixed_and_bounded(game: dict[str, object]) -> None:
    """A long run crosses tile/chunk seams without gaps, moving tiles or retaining old sections."""
    stage, dino = cast(Stage, game["stage"]), cast(Sprite, game["dino"])
    # Keep this run obstacle-free so it can exercise several complete floor sections.
    game["playing"] = True
    dino.stop()
    ticks(stage, 30)
    original = cast(list[TileMap], game["ground"])[0]
    original_position = (original.x, original.y)
    max_sections = 0
    for _ in range(1600):
        ticks(stage, 1)
        sections = cast(list[TileMap], game["ground"])
        max_sections = max(max_sections, len(sections))
        assert sections[0].bounds.left <= stage.world_bounds.left
        assert sections[-1].bounds.right >= stage.world_bounds.right
        assert all(a.bounds.right == b.bounds.left for a, b in pairwise(sections))
        assert (original.x, original.y) == original_position
        assert dino.body.grounded
        assert dino.y == pytest.approx(-135, abs=2)
        assert stage.camera[1] == 0
    assert dino.x > 6000 and max_sections <= 3
    assert original not in stage.objects
    key(stage, Key.R)
    ticks(stage, 2)
    assert dino.x < -240 and stage.camera[0] < 20
    assert len(cast(list[TileMap], game["ground"])) == 2
    assert len(stage._actions) == 1


def test_floor_pixels_follow_camera_without_moving_tiles(game: dict[str, object]) -> None:
    """Rendering subtracts the camera from fixed world tiles; overlays retain screen coordinates."""
    stage = cast(Stage, game["stage"])
    stage._target = pygame.display.set_mode((stage.width, stage.height))
    section = cast(list[TileMap], game["ground"])[0]
    position = (section.x, section.y)
    frame(stage)
    before = stage._target.copy()
    stage.camera = (32, 0)
    frame(stage)
    # A whole tile camera shift preserves the repeating floor, below its top at screen y=355.
    assert pygame.image.tobytes(
        before.subsurface((50, 360, 700, 20)), "RGBA"
    ) == pygame.image.tobytes(stage._target.subsurface((50, 360, 700, 20)), "RGBA")
    assert (section.x, section.y) == position
    assert stage.to_screen((section.x, section.y))[0] == pytest.approx(-64)


@pytest.mark.parametrize("kind", ("cactus", "rock"))
def test_jump_clears_a_stationary_obstacle(game: dict[str, object], kind: str) -> None:
    """A normally timed jump clears a fixed obstacle and lands beyond it without moving it."""
    stage, dino = cast(Stage, game["stage"]), cast(Sprite, game["dino"])
    game["choice"] = lambda kinds: kind
    ticks(stage, 100)
    obstacle = cast(list[Sprite], game["obstacles"])[0]
    fixed_position = obstacle.position
    dino.stop()
    while obstacle.x - dino.x > 120:
        ticks(stage, 1)
        assert game["playing"]
    key(stage, Key.SPACE)
    ticks(stage, 75)
    assert game["playing"] and dino.body.grounded
    assert dino.x > obstacle.x + 50
    assert obstacle.position == fixed_position
