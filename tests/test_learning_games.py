"""Exercise the actual learning games without adding debug APIs to their source."""

import ast
import runpy
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pygame
import pytest

from plocks import (
    BodyType,
    Costume,
    GamepadPress,
    Key,
    MouseButton,
    Sprite,
    Stage,
    TiledBackground,
    TileMap,
)
from plocks._render import frame
from plocks._runtime import advance, close
from plocks._scripts import _step, _trigger

GAMES = (
    "jungle_run",
    "mario",
    "fruit_ninja",
    "platformer",
    "geometry_dash",
    "snake_run",
    "temple_run",
    "scrolling_world",
)
TUTORIALS = (*GAMES, "asset_workshop", "dino_run", "maze_quest", "swing_lab", "robot_workshop")
ROOT = Path(__file__).parents[1]


@pytest.fixture
def load_game(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[str], Stage]]:
    """Load the examples from an unrelated cwd without any launcher assistance."""
    monkeypatch.chdir(tmp_path)
    stages: list[Stage] = []

    def load(name: str) -> Stage:
        def capture(stage: Stage) -> None:
            stages.append(stage)

        with patch.object(Stage, "run", capture):
            runpy.run_path(str(ROOT / "src/plocks/_games" / name / "main.py"), run_name="__main__")
        stage = stages[-1]
        stage._state = "running"
        for handler in tuple(stage._starts):
            _trigger(stage, handler)
        _step(stage)
        stage._last_wall = 0
        return stage

    yield load
    for stage in stages:
        close(stage)


def state(stage: Stage) -> dict[str, object]:
    """Read the module variables used by callbacks without adding game test hooks."""
    return dict[str, object](stage._updates[0][1].__globals__)


def ticks(stage: Stage, count: int) -> None:
    """Advance the real engine order with a synthetic wall clock."""
    for _ in range(count):
        advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)


def press(stage: Stage, key: Key) -> None:
    """Dispatch a key transition and leave it held until explicitly released."""
    stage._held_keys.add(key)
    stage._pending.append(GamepadPress(stage.gamepads[0], stage.gamepads[0]._key_buttons[key]))
    ticks(stage, 1)


def test_workshop_keeps_independent_default_player_controls(
    load_game: Callable[[str], Stage],
) -> None:
    """A migrated reset button must not remap player one's stick onto player two's keys."""
    stage = load_game("asset_workshop")
    one, two = stage.gamepads[:2]
    stage._held_keys.add(Key.D)
    assert one.left_stick == (1, 0) and two.left_stick == (0, 0)
    stage._held_keys.clear()
    stage._held_keys.add(Key.RIGHT)
    assert one.left_stick == (0, 0) and two.left_stick == (1, 0)


@pytest.mark.parametrize("name", TUTORIALS)
def test_games_render_and_close_from_another_folder(
    name: str, load_game: Callable[[str], Stage]
) -> None:
    """All games load static assets, run, render and retire their scene and actions."""
    stage = load_game(name)
    stage._target = pygame.display.set_mode((stage.width, stage.height))
    ticks(stage, 120)
    frame(stage)
    assert stage.time == pytest.approx(2)
    assert stage._target.get_at((0, 0)).a == 255
    actors = [obj for obj in stage.objects if isinstance(obj, Sprite)]
    close(stage)
    assert not stage.objects and not stage._actions and not stage._voices
    assert all(actor._stage is None for actor in actors)


def test_collection_is_focused_games_and_workshop_without_artwork_code() -> None:
    """The teaching surface stays small, self-contained and free from image generation."""
    assert {
        p.name
        for p in (ROOT / "src/plocks/_games").iterdir()
        if p.is_dir() and p.name != "__pycache__"
    } == set(TUTORIALS)
    for name in TUTORIALS:
        folder = ROOT / "src/plocks/_games" / name
        tree = ast.parse((folder / "main.py").read_text())
        for node in ast.walk(tree):
            assert not isinstance(node, ast.Nonlocal)
            if isinstance(node, ast.FunctionDef):
                assert node.name != "main"
                if node.decorator_list:
                    assert node in tree.body, "Message handlers belong at module level"
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module is not None and not node.module.startswith(("PIL", "pygame"))
            elif isinstance(node, ast.Import):
                assert all(not alias.name.startswith(("PIL", "pygame")) for alias in node.names)
        assert (folder / "README.md").is_file()
        assert list((folder / "assets").glob("*.png"))


def test_mario_jump_coin_stomp_gap_and_restart(load_game: Callable[[str], Stage]) -> None:
    """Jumping lands; collecting and stomping remove actors; falling and restart reset state."""
    stage = load_game("mario")
    hero = cast(Sprite, state(stage)["hero"])
    press(stage, Key.SPACE)
    ticks(stage, 10)
    assert hero.y > -80
    ticks(stage, 50)
    assert hero.y == -128 and state(stage)["on_ground"]
    coin = cast(list[Sprite], state(stage)["coins"])[0]
    hero.position = coin.position
    ticks(stage, 1)
    assert state(stage)["score"] == 1 and coin not in stage.objects
    enemy = cast(list[Sprite], state(stage)["enemies"])[0]
    hero.position = (enemy.x, enemy.bounds.top + 1)
    ticks(stage, 12)
    assert enemy not in stage.objects and state(stage)["outcome"] == "playing"
    hero.position = (425, -310)
    ticks(stage, 1)
    assert state(stage)["outcome"] == "Mind the gap!"
    press(stage, Key.R)
    assert state(stage)["score"] == 0 and len(cast(list[Sprite], state(stage)["coins"])) == 9
    hero.position = (1555, -128)
    ticks(stage, 1)
    assert state(stage)["outcome"] == "You reached the flag!"


def test_mario_ceiling_and_wall_stop_motion(load_game: Callable[[str], Stage]) -> None:
    """Tile geometry stops upward and horizontal movement without allowing an air jump."""
    stage = load_game("mario")
    hero = cast(Sprite, state(stage)["hero"])
    hero.position = (20, -128)
    press(stage, Key.SPACE)
    ticks(stage, 8)
    assert hero.bounds.top <= -64
    assert cast(float, state(stage)["speed_y"]) <= 0
    hero.position = (-32, -44)
    press(stage, Key.RIGHT)
    ticks(stage, 3)
    assert hero.bounds.right <= -16


def test_platformer_ground_jump_checkpoint_and_respawn(load_game: Callable[[str], Stage]) -> None:
    """The physics solver grounds and jumps the player; checkpoint controls respawn."""
    stage = load_game("platformer")
    hero = cast(Sprite, state(stage)["hero"])
    lift = next(
        obj
        for obj in stage.objects
        if isinstance(obj, Sprite) and obj.body_type == BodyType.KINEMATIC
    )
    ticks(stage, 20)
    assert hero.body.grounded
    y = hero.y
    press(stage, Key.SPACE)
    ticks(stage, 10)
    assert hero.y > y + 20 and not hero.body.grounded
    assert lift.y > -110
    hero.position = (180, 62)
    hero.body.velocity = (0, 0)
    ticks(stage, 2)
    assert state(stage)["saved"] is True
    hero.y = -310
    ticks(stage, 1)
    assert hero.x == 180 and hero.y > 50 and state(stage)["falls"] == 1
    press(stage, Key.R)
    assert hero.x == -300 and state(stage)["saved"] is False


def test_fruit_swipe_halves_bomb_and_restart(load_game: Callable[[str], Stage]) -> None:
    """A fast swipe cuts once, creates halves, and a bomb remains fatal in that frame."""
    stage = load_game("fruit_ninja")
    flying = cast(list[tuple[Sprite, float, float, float, str]], state(stage)["flying"])
    costumes = cast(dict[str, Costume], state(stage)["costumes"])
    apple = Sprite(costumes["apple"])
    stage.add(apple)
    flying.append((apple, 0, 0, 0, "apple"))
    stage.mouse._down.add(MouseButton.LEFT)
    stage.mouse._position = (-100, 0)
    ticks(stage, 1)
    assert apple in stage.objects  # Pressing alone is not a swipe.
    stage.mouse._position = (100, 0)
    ticks(stage, 1)
    assert apple not in stage.objects and state(stage)["score"] == 1
    assert sum(item[4] == "half" for item in flying) == 2
    bomb = Sprite(costumes["bomb"])
    stage.add(bomb)
    flying.append((bomb, 0, 0, 0, "bomb"))
    stage.mouse._position = (-100, 0)
    ticks(stage, 1)
    assert state(stage)["over"] is True
    press(stage, Key.R)
    assert state(stage)["score"] == 0 and state(stage)["over"] is False
    assert len(flying) <= 1


def test_dash_crash_jump_and_finish(load_game: Callable[[str], Stage]) -> None:
    """Running fails on obstacles; a correctly timed jump clears the first spike."""
    stage = load_game("geometry_dash")
    hero = cast(Sprite, state(stage)["hero"])
    ticks(stage, 80)
    assert state(stage)["outcome"] == "Crash!"
    press(stage, Key.R)
    ticks(stage, 45)
    press(stage, Key.SPACE)
    ticks(stage, 30)
    assert hero.x > 40 and state(stage)["outcome"] == "playing"
    hero.x = 2200
    ticks(stage, 1)
    assert state(stage)["outcome"] == "Course complete!"


def test_snake_collects_shrinks_and_restarts(load_game: Callable[[str], Stage]) -> None:
    """Perspective objects project toward the player and resolve once at the crossing."""
    stage = load_game("snake_run")
    head = cast(Sprite, state(stage)["head"])
    ticks(stage, 90)
    assert state(stage)["score"] == 1
    assert len(cast(list[Sprite], state(stage)["segments"])) == 4
    head.x = 145
    ticks(stage, 103)
    assert len(cast(list[Sprite], state(stage)["segments"])) == 2
    press(stage, Key.R)
    assert state(stage)["score"] == 0 and len(cast(list[float], state(stage)["history"])) == 64
    assert len(cast(list[Sprite], state(stage)["segments"])) == 3


def test_world_camera_parallax_and_editing(load_game: Callable[[str], Stage]) -> None:
    """Painting accounts for camera translation and layers scroll at different speeds."""
    stage = load_game("scrolling_world")
    hero = cast(Sprite, state(stage)["hero"])
    hero.x = 400
    ticks(stage, 1)
    assert stage.camera == (400, 0)
    backgrounds = [obj for obj in stage.objects if isinstance(obj, TiledBackground)]
    assert [obj.offset[0] for obj in backgrounds] == [-40, -120, -240]
    world = next(obj for obj in stage.objects if isinstance(obj, TileMap))
    press(stage, Key.THREE)
    stage._pending.append(((0, 0), MouseButton.LEFT))
    ticks(stage, 1)
    assert world.get_tile(row=7, column=25) == "S"
    stage._pending.append(((0, 0), MouseButton.RIGHT))
    ticks(stage, 1)
    assert world.get_tile(row=7, column=25) is None


@pytest.mark.parametrize("name", [name for name in GAMES if name != "scrolling_world"])
def test_restarts_do_not_accumulate_actors_or_actions(
    name: str, load_game: Callable[[str], Stage]
) -> None:
    """Replaying a game keeps bounded scene membership and live behavior ownership."""
    stage = load_game(name)
    ticks(stage, 2)
    members, actions = len(stage.objects), len(stage._actions)
    for _ in range(8):
        press(stage, Key.R)
        ticks(stage, 2)
        assert len(stage.objects) == members
        assert len(stage._actions) <= actions


@pytest.mark.parametrize("name", ["mario", "snake_run"])
def test_later_asset_loads_survive_a_changed_cwd(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Relative entry scripts keep absolute asset paths after the working directory changes."""
    stages: list[Stage] = []

    def capture(stage: Stage) -> None:
        stages.append(stage)

    monkeypatch.chdir(ROOT / "src/plocks/_games" / name)
    with patch.object(Stage, "run", capture):
        runpy.run_path("main.py", run_name="__main__")
    monkeypatch.chdir(tmp_path)
    stage = stages[0]
    stage._state = "running"
    stage._last_wall = 0
    try:
        ticks(stage, 95)
        press(stage, Key.R)
        assert stage.running and stage.objects
    finally:
        close(stage)


def temple_step(stage: Stage, *, skip: str = "") -> None:
    """Play the next course event using the game's real keyboard handlers."""
    values = state(stage)
    hero = cast(Sprite, values["hero"])
    objects = cast(list[tuple[Sprite, int, int, str]], values["objects"])
    if objects:
        _, location, lane, kind = objects[0]
        ahead = location - cast(float, values["distance"])
        key = None
        if kind == "coin" and hero.x != lane * 145:
            key = Key.RIGHT if hero.x < lane * 145 else Key.LEFT
        elif kind == "hurdle" and 30 < ahead <= 34:
            key = Key.SPACE
        elif kind == "arch" and 42 < ahead <= 46:
            key = Key.DOWN
        elif kind in ("left", "right") and ahead <= 45:
            key = Key.LEFT if kind == "left" else Key.RIGHT
        if key is not None and kind != skip:
            stage._pending.append(
                GamepadPress(stage.gamepads[0], stage.gamepads[0]._key_buttons[key])
            )
    ticks(stage, 1)


def test_temple_complete_course_collects_all_coins(load_game: Callable[[str], Stage]) -> None:
    """A real-input run clears every hurdle, arch and corner and collects all eight coins."""
    stage = load_game("temple_run")
    headings: set[int] = set()
    for _ in range(1100):
        temple_step(stage)
        headings.add(cast(int, state(stage)["heading"]))
        if state(stage)["outcome"] != "playing":
            break
    assert state(stage)["outcome"] == "Temple reached! Well run."
    assert state(stage)["score"] == 8
    assert headings == {0, 3}
    assert not state(stage)["objects"] and not stage._actions


@pytest.mark.parametrize(
    "skip,reason",
    [
        ("hurdle", "Jump over"),
        ("arch", "Slide under"),
        ("left", "Missed the corner"),
    ],
)
def test_temple_mistakes_end_run_and_restart(
    skip: str, reason: str, load_game: Callable[[str], Stage]
) -> None:
    """Required maneuvers cannot be bypassed by lane changes; restart resets all progress."""
    stage = load_game("temple_run")
    for _ in range(850):
        temple_step(stage, skip=skip)
        if state(stage)["outcome"] != "playing":
            break
    assert str(state(stage)["outcome"]).startswith(reason)
    distance = state(stage)["distance"]
    ticks(stage, 20)
    assert state(stage)["distance"] == distance
    press(stage, Key.R)
    assert state(stage)["score"] == 0 and state(stage)["heading"] == 0
    assert state(stage)["outcome"] == "playing"
    assert len(cast(list[object], state(stage)["objects"])) == 15
    assert not stage._actions


def test_temple_turn_window_wrong_turn_and_hidden_path(load_game: Callable[[str], Stage]) -> None:
    """Early input changes lanes; the matching turn reveals the next stretch, wrong input fails."""
    stage = load_game("temple_run")
    press(stage, Key.LEFT)
    assert cast(Sprite, state(stage)["hero"]).x == -145
    assert state(stage)["heading"] == 0
    while cast(float, state(stage)["distance"]) < 620:
        temple_step(stage)
    objects = cast(list[tuple[Sprite, int, int, str]], state(stage)["objects"])
    assert all(not actor.visible for actor, location, _, _ in objects if location > 680)
    press(stage, Key.RIGHT)
    assert str(state(stage)["outcome"]).startswith("Wrong turn!")
    press(stage, Key.R)
    while cast(float, state(stage)["distance"]) < 620:
        temple_step(stage)
    press(stage, Key.LEFT)
    assert state(stage)["heading"] == 3
    objects = cast(list[tuple[Sprite, int, int, str]], state(stage)["objects"])
    assert any(actor.visible for actor, location, _, _ in objects if location > 680)


def test_temple_actions_pause_and_busy_input(load_game: Callable[[str], Stage]) -> None:
    """Jump/slide scripts exclude each other; pause freezes both the runner and course."""
    stage = load_game("temple_run")
    hero = cast(Sprite, state(stage)["hero"])
    press(stage, Key.SPACE)
    ticks(stage, 10)
    action = state(stage)["maneuver"]
    press(stage, Key.DOWN)
    assert state(stage)["maneuver"] is action and hero.y > -110
    stage.pause()
    position, distance = hero.position, state(stage)["distance"]
    ticks(stage, 60)
    assert hero.position == position and state(stage)["distance"] == distance
    stage.resume()
    ticks(stage, 40)
    assert hero.y == -110
    press(stage, Key.DOWN)
    ticks(stage, 2)
    assert hero.costume.height == 28
    press(stage, Key.SPACE)
    ticks(stage, 10)
    assert hero.y == -110 and hero.costume.height == 28
    press(stage, Key.R)
    assert hero.costume.height == 48 and not stage._actions


@pytest.mark.parametrize("name", TUTORIALS)
def test_importing_example_prepares_game_without_starting(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Module-level setup registers handlers; only the __main__ guard opens the game."""
    filename = ROOT / "src/plocks/_games" / name / "main.py"
    monkeypatch.chdir(tmp_path)
    with patch.object(Stage, "run") as start:
        namespace = runpy.run_path(str(filename), run_name="imported_example")
    stage = cast(Stage, namespace["stage"])
    try:
        start.assert_not_called()
        assert stage._state == "new"
        if name != "fruit_ninja":
            assert stage.objects
        if name not in ("maze_quest", "swing_lab"):
            assert stage._updates and stage._draws
        elif name == "maze_quest":
            assert stage._touches and stage._starts
        else:
            assert stage._physics is not None and stage.physics._connections and stage._draws
        assert not pygame.display.get_init()
        for _, callback in stage._updates:
            assert callback.__closure__ is None
            assert callback.__globals__["stage"] is stage
    finally:
        close(stage)
    assert not stage.objects and not stage._actions and stage._target is None
