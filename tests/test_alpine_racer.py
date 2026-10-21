"""Play the actual five-minute racer through its public input and engine loop."""

import runpy
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import cast

import pygame
import pytest
from PIL import Image as PillowImage

from plocks import Canvas, Color, Gamepad, GamepadPress, Image, Key, Point, Sprite, Stage
from plocks._render import frame
from plocks._runtime import advance, close
from plocks._scripts import _step, _trigger

ROOT = Path(__file__).parents[1]
GAME = ROOT / "src/plocks/_games/alpine_racer"
type Rival = tuple[Sprite, float, float, float]


@pytest.fixture
def game(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, object]]:
    """Load from another directory, acquire no window, and close the real scene afterward."""
    monkeypatch.chdir(tmp_path)
    namespace = runpy.run_path(str(GAME / "main.py"))
    stage = cast(Stage, namespace["stage"])
    stage._state = "running"
    stage._last_wall = 0
    namespace = stage._updates[0][1].__globals__
    for handler in tuple(stage._starts):
        _trigger(stage, handler)
    _step(stage)
    yield namespace
    close(stage)
    assert not stage.objects and not stage._actions and not stage._voices


def ticks(stage: Stage, count: int) -> None:
    """Advance complete fixed steps, including real input, updates and rendering preparation."""
    for _ in range(count):
        advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)


def key(stage: Stage, pressed: Key) -> None:
    """Dispatch pause/restart through their real mapped-button registration."""
    slot = stage.gamepads[0]
    stage._pending.append(GamepadPress(slot, slot._key_buttons[pressed]))
    ticks(stage, 1)


def test_waiting_acceleration_steering_and_depth(game: dict[str, object]) -> None:
    """The clock waits for acceleration; held steering selects matching car art and moves the road."""
    stage, car = cast(Stage, game["stage"]), cast(Sprite, game["car"])
    remaining = cast(Callable[[], float], game["time_left"])
    images = cast(dict[str, Image], game["car_images"])
    ticks(stage, 120)
    assert game["distance"] == 0 and remaining() == 300
    assert not stage.paused and stage._physics is None and stage.camera == (0, 0)
    stage._held_keys.update({Key.W, Key.LEFT})
    ticks(stage, 60)
    assert cast(float, game["speed"]) > 170 and cast(float, game["lane"]) < 0
    assert car.image is images["left"]
    stage._held_keys.remove(Key.LEFT)
    stage._held_keys.add(Key.RIGHT)
    ticks(stage, 1)
    assert car.image is images["right"]
    stage._held_keys.remove(Key.RIGHT)
    ticks(stage, 1)
    assert car.image is images["straight"]
    project = cast(Callable[[float, float], tuple[float, float, float]], game["project"])
    near, far = project(100, 0), project(1000, 0)
    assert near[1] < far[1] < 80 and near[2] > far[2] > 0
    assert 298 < remaining() < 300


def test_road_markings_and_rivals_advance_and_render(game: dict[str, object]) -> None:
    """Travel changes real road-strip art and projected positions while keeping scene size fixed."""
    stage = cast(Stage, game["stage"])
    road = cast(list[tuple[Sprite, Image, Image]], game["road"])
    before = [(s.x, s.y, s.image) for s, _, _ in road]
    members = len(stage.objects)
    stage._held_keys.add(Key.W)
    ticks(stage, 180)
    assert cast(float, game["distance"]) > 240
    assert len(stage.objects) == members
    assert any(s.x != x or s.image is not image for (s, _, _), (x, _, image) in zip(road, before))
    assert all(s.y == y for (s, _, _), (_, y, _) in zip(road, before))
    stage._target = pygame.display.set_mode((stage.width, stage.height))
    frame(stage)
    assert stage._target.get_at((480, 430)) != stage._target.get_at((10, 20))


def test_grass_brakes_and_collision_cooldown(game: dict[str, object]) -> None:
    """Grass/braking slow the player, and one rival bump cannot repeatedly halve speed each tick."""
    stage = cast(Stage, game["stage"])
    stage._held_keys.add(Key.W)
    game["speed"], game["lane"] = 200.0, 1.05
    ticks(stage, 60)
    assert 85 < cast(float, game["speed"]) < 95
    stage._held_keys.clear()
    stage._held_keys.add(Key.DOWN)
    ticks(stage, 30)
    assert cast(float, game["speed"]) < 100
    stage._held_keys.clear()
    stage._held_keys.add(Key.W)
    game["speed"], game["lane"] = 200.0, 0.0
    rivals = cast(list[Rival], game["rivals"])
    actor, _, _, cruise = rivals[0]
    rivals[0] = (actor, 0.0, cast(float, game["distance"]) + 20, cruise)
    ticks(stage, 1)
    deadline = cast(float, game["bump_until"])
    assert cast(float, game["speed"]) < 100 and deadline > stage.time
    ticks(stage, 15)
    assert 125 < cast(float, game["speed"]) < 150
    assert game["bump_until"] == deadline


def test_complete_five_minute_race_pause_and_restart(
    game: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The unshortened 300-second race finishes on simulation time and restarts without leaked cars."""
    stage = cast(Stage, game["stage"])
    remaining = cast(Callable[[], float], game["time_left"])
    members = len(stage.objects)
    assert game["RACE_SECONDS"] == 300
    stage._held_keys.add(Key.W)
    game["lane"] = 0.92  # A clear line beside the rivals, just inside the grass edge.

    def countersteer(slot: Gamepad) -> tuple[float, float]:
        # A simple analogue driver steers toward a clear line; it still uses real controls.
        steering = max(-1.0, min(1.0, (0.92 - cast(float, game["lane"])) * 40))
        return steering, 1.0 if Key.W in stage._held_keys else 0.0

    monkeypatch.setattr(Gamepad, "left_stick", property(countersteer))
    ticks(stage, 60)
    key(stage, Key.P)
    paused = (stage.time, remaining(), game["distance"])
    ticks(stage, 100)
    assert (stage.time, remaining(), game["distance"]) == paused
    key(stage, Key.P)
    for _ in range(18005):
        ticks(stage, 1)
        if stage.paused:
            break
    assert remaining() == 0 and stage.paused
    assert stage.time == pytest.approx(300, abs=0.02)
    assert cast(float, game["distance"]) > 800000
    # A clean run can beat every rival; first place must be reachable before time expires.
    assert all(
        location < cast(float, game["distance"])
        for _, _, location, _ in cast(list[Rival], game["rivals"])
    )
    assert len(stage.objects) == members
    key(stage, Key.R)
    assert not stage.paused and game["started_at"] is None
    assert game["distance"] == 0 and remaining() == 300
    for _ in range(8):
        key(stage, Key.R)
        assert len(stage.objects) == members
    assert len(cast(list[Rival], game["rivals"])) == 5


def test_static_steering_art_has_consistent_transparent_anchors() -> None:
    """The three actual PNG views have matching dimensions and distinct left/right silhouettes."""
    with (
        PillowImage.open(GAME / "assets/car_straight.png") as straight,
        PillowImage.open(GAME / "assets/car_left.png") as left,
        PillowImage.open(GAME / "assets/car_right.png") as right,
    ):
        assert straight.size == left.size == right.size == (192, 128)
        assert straight.mode == left.mode == right.mode == "RGBA"
        assert left.tobytes() != right.tobytes()
        assert left.transpose(PillowImage.Transpose.FLIP_LEFT_RIGHT).tobytes() == right.tobytes()
        assert left.getpixel((0, 0)) == right.getpixel((0, 0)) == (0, 0, 0, 0)


@pytest.mark.parametrize("side", (-1, 1))
def test_offroad_standstill_can_accelerate_and_steer_home(
    game: dict[str, object], side: int
) -> None:
    """Neither grass drag nor stopped-car steering can trap a racer beyond either road edge."""
    stage = cast(Stage, game["stage"])
    game["lane"], game["speed"] = side * 1.6, 0.0
    stage._held_keys.add(Key.W)
    ticks(stage, 60)
    assert cast(float, game["speed"]) >= 85
    # Even after stopping completely, steering must still work without throttle.
    game["speed"] = 0.0
    stage._held_keys.clear()
    steering = Key.LEFT if side > 0 else Key.RIGHT
    stage._held_keys.add(steering)
    ticks(stage, 30)
    assert abs(cast(float, game["lane"])) < 1.5
    assert game["speed"] == 0
    stage._held_keys.add(Key.W)
    for _ in range(300):
        ticks(stage, 1)
        if abs(cast(float, game["lane"])) < 0.8:
            break
    assert abs(cast(float, game["lane"])) < 0.8
    assert cast(float, game["speed"]) > 0
    assert game["started_at"] is not None and not stage.paused


def test_top_speed_has_fast_forward_flow(game: dict[str, object]) -> None:
    """360 km/h advances 100 metres each second, with visibly fast nearby scenery."""
    stage = cast(Stage, game["stage"])
    project = cast(Callable[[float, float], tuple[float, float, float]], game["project"])
    game["speed"], game["lane"] = 360.0, 0.0
    rivals = cast(list[Rival], game["rivals"])
    for actor, _, _, _ in rivals:
        stage.remove(actor)
    rivals.clear()  # Measure unobstructed travel independently of overtaking collisions.
    before = project(600, 1.35)
    stage._held_keys.add(Key.W)
    ticks(stage, 8)
    travelled = cast(float, game["distance"])
    after = project(600 - travelled, 1.35)
    assert travelled == pytest.approx(400)
    assert before[1] - after[1] > 70
    assert after[2] > 2 * before[2]
    ticks(stage, 52)
    assert game["speed"] == 360
    assert game["distance"] == pytest.approx(3000)
    assert cast(float, game["TRACK_LENGTH"]) == 60000


@pytest.mark.parametrize("side", (-1, 1))
@pytest.mark.parametrize("lap", (0, 1))
def test_tree_trunks_block_until_we_steer_away(
    game: dict[str, object], side: int, lap: int
) -> None:
    """High-speed trunk collisions stop travel even after cooldown; steering frees the car."""
    stage = cast(Stage, game["stage"])
    tree_image = cast(Image, game["tree_image"])
    track = cast(float, game["TRACK_LENGTH"])
    game["distance"] = lap * track + 300.0
    game["speed"], game["lane"] = 360.0, side * 1.35
    scenery = cast(list[tuple[Sprite, float, float]], game["scenery"])
    # Put the farther tree first to prove nearest contact wins regardless of list order.
    trees = [item for item in scenery if item[0].image is tree_image and item[2] * side > 0]
    scenery[:] = list(reversed(trees))
    stage._held_keys.add(Key.W)
    ticks(stage, 120)
    assert game["distance"] == pytest.approx(lap * track + 535)
    assert game["speed"] == 0
    assert any(actor.visible for actor, _, _ in scenery)
    stage._held_keys.add(Key.LEFT if side > 0 else Key.RIGHT)
    ticks(stage, 120)
    assert abs(cast(float, game["lane"])) < 0.95
    assert cast(float, game["distance"]) > lap * track + 535
    assert cast(float, game["speed"]) > 0


def test_tree_collision_sweeps_steps_and_lap_seam(game: dict[str, object]) -> None:
    """The full travelled interval is checked, including the start/end seam of the circuit."""
    drive = cast(Callable[[float], None], game["drive_forward"])
    track = cast(float, game["TRACK_LENGTH"])
    game["distance"], game["speed"], game["lane"] = track - 200, 360.0, 1.35
    drive(0.25)  # Travel would pass the trunk entirely if only the endpoint were checked.
    assert game["distance"] == pytest.approx(track - 65)
    assert game["speed"] == 0
    game["speed"] = 90.0
    drive(0.25)
    assert game["distance"] == pytest.approx(track - 65)
    # Grass away from the trunks remains traversable; foliage is not a solid rectangle.
    game["speed"], game["lane"] = 90.0, 1.05
    drive(0.25)
    assert cast(float, game["distance"]) > track - 65


@pytest.mark.parametrize("origin, outward", ((15000, -1), (45000, 1)))
def test_sharp_bends_require_countersteering_or_lower_speed(
    game: dict[str, object], origin: int, outward: int
) -> None:
    """Opposite bends push a fast car outward; slowing down or steering into the corner helps."""
    stage = cast(Stage, game["stage"])
    game["started_at"] = 0.0
    game["distance"], game["speed"], game["lane"] = float(origin), 360.0, 0.0
    ticks(stage, 30)
    fast_drift = cast(float, game["lane"])
    assert fast_drift * outward > 0.2
    game["distance"], game["speed"], game["lane"] = float(origin), 90.0, 0.0
    ticks(stage, 30)
    slow_drift = cast(float, game["lane"])
    assert 0 < slow_drift * outward < abs(fast_drift) / 5
    game["distance"], game["speed"], game["lane"] = float(origin), 360.0, 0.0
    stage._held_keys.add(Key.RIGHT if outward < 0 else Key.LEFT)
    ticks(stage, 30)
    assert cast(float, game["lane"]) * outward < 0


def test_difficult_course_keeps_the_previous_flat_renderer(game: dict[str, object]) -> None:
    """Only bends and driving difficulty change; the hill renderer and moving horizon are gone."""
    assert "COURSE" not in game and "horizon" not in game and "show_ground" not in game
    background = cast(Sprite, game["background"])
    road = cast(list[tuple[Sprite, Image, Image]], game["road"])
    show = cast(Callable[[], None], game["show_road"])
    positions = [strip.y for strip, _, _ in road]
    for at in (0, 15000, 22000, 45000, 60000):
        game["distance"] = float(at)
        show()
        assert background.y == 20 and background.scale == 1
        assert [strip.y for strip, _, _ in road] == positions
    assert len(road) == 69


@pytest.mark.parametrize("origin", (15000, 45000))
def test_corner_push_is_half_again_as_strong(
    game: dict[str, object], monkeypatch: pytest.MonkeyPatch, origin: int
) -> None:
    """The new setting increases outward movement by 50 percent under identical driving input."""
    stage = cast(Stage, game["stage"])
    assert game["CORNER_PUSH"] == 6
    game["started_at"] = 0.0
    changes: list[float] = []
    for strength in (4, 6):
        monkeypatch.setitem(game, "CORNER_PUSH", strength)
        game["distance"], game["speed"], game["lane"] = float(origin), 360.0, 0.0
        ticks(stage, 10)
        changes.append(cast(float, game["lane"]))
    assert changes[1] == pytest.approx(changes[0] * 1.5)


@pytest.mark.parametrize("origin", (0, 15000, 45000))
def test_map_geometry_matches_the_road_projection(game: dict[str, object], origin: int) -> None:
    """The route uses one uniform scale and agrees with the local bend seen in the main view."""
    point = cast(Callable[[float], Point], game["map_point"])
    center = cast(Callable[[float], float], game["road_center"])
    project = cast(Callable[[float, float], tuple[float, float, float]], game["project"])
    scale = 90 / 60000
    game["distance"], game["lane"] = float(origin), 0.0
    start, next_point = point(origin), point(origin + 1)
    for ahead in (150, 600, 2500):
        end = point(origin + ahead)
        assert end[0] - start[0] == pytest.approx(ahead * scale)
        assert end[1] - start[1] == pytest.approx((center(origin + ahead) - center(origin)) * scale)
        map_bend = (end[1] - start[1] - ahead * (next_point[1] - start[1])) / scale
        x, _, visual_scale = project(ahead, 0)
        assert x == pytest.approx(map_bend * visual_scale, abs=1e-8)


def test_drawn_route_and_all_markers_share_the_actual_road(
    game: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The HUD joins actual road samples and wraps every racer's marker onto the same lap."""
    stage = cast(Stage, game["stage"])
    point = cast(Callable[[float], Point], game["map_point"])
    rivals = cast(list[Rival], game["rivals"])
    game["distance"] = 75000.0
    for index, (actor, sideways, _, cruise) in enumerate(rivals):
        rivals[index] = (actor, sideways, float(61000 + index * 12000), cruise)
    lines: list[tuple[Point, Point]] = []
    dots: list[tuple[Point, Color]] = []

    def record_line(
        canvas: Canvas, start: Point, end: Point, *, color: Color = "white", width: int = 1
    ) -> None:
        assert width == 2 and color == "#a2b2b9"
        lines.append((start, end))

    def record_circle(
        canvas: Canvas, center: Point, radius: float, *, color: Color = "white", width: int = 0
    ) -> None:
        dots.append((center, color))

    monkeypatch.setattr(Canvas, "line", record_line)
    monkeypatch.setattr(Canvas, "circle", record_circle)
    stage._target = pygame.display.set_mode((stage.width, stage.height))
    frame(stage)
    assert len(lines) == 128
    for index, (start, end) in enumerate(lines):
        assert start == point(60000 * index / 128)
        assert end == point(60000 * (index + 1) / 128)
        assert 350 < start[0] < 460 and -220 < start[1] < -125
    assert lines[0][0][0] == 360 and lines[-1][1][0] == 450
    assert [position for position, _ in dots[:-1]] == [
        point(location % 60000) for _, _, location, _ in rivals
    ]
    assert all(color == "#72c4ff" for _, color in dots[:-1])
    assert dots[-1] == (point(15000), "#ffac43")
