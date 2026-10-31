"""Continuous, read-only physics queries and their beginner convenience methods."""

import pytest

from plocks import (
    BodyType,
    Box,
    CastIgnore,
    CastTarget,
    Circle,
    Image,
    PhysicsError,
    Sprite,
    Stage,
    TileMap,
)
from plocks._runtime import close


def test_thin_tile_sweep_first_path() -> None:
    """A clear destination cannot hide a thin tile crossed by the body."""
    stage = Stage(physics=True)
    actor = Sprite(Image.rectangle(10, 10))
    wall = TileMap(["#"], {"#": Image.rectangle(2, 40)}, tile_size=(2, 40), solid={"#"}, x=50, y=20)
    stage.add(actor)
    stage.add(wall)
    before = actor.position, actor.body.velocity, tuple(stage.objects)
    try:
        assert actor.body.can_fit_shape(Box(10, 10, center=(100, 0)))
        hit = actor.body.shape_cast(distance=100, direction=90)
        assert hit is not None and hit.target is wall and hit.cell == (0, 0)
        assert hit.distance == pytest.approx(45)
        assert hit.point == pytest.approx((50, 0))
        assert hit.normal == pytest.approx((-1, 0))
        assert not actor.body.can_travel(distance=100, direction=90)
        assert actor.body.can_travel(distance=40, direction=90)
        ray = stage.physics.raycast((0, 0), (100, 0), ignore=(actor,))
        assert ray is not None and ray.distance == pytest.approx(50)
        assert (actor.position, actor.body.velocity, tuple(stage.objects)) == before
    finally:
        close(stage)


@pytest.mark.parametrize("source", [Box(10, 10), Circle(5)])
def test_round_targets_and_misses(source: Box | Circle) -> None:
    """Box and circle sweeps use rounded target corners, not an expanded AABB."""
    stage = Stage(physics=True)
    target = Sprite(Image.rectangle(10, 10), x=50, body_type=BodyType.STATIC)
    stage.add(target)
    target.body.shape = Circle(5)
    try:
        hit = stage.physics.shape_cast(source, start=(0, 0), end=(100, 0))
        assert hit is not None and hit.distance == pytest.approx(40)
        assert hit.point == pytest.approx((45, 0)) and hit.cell is None
        assert stage.physics.shape_cast(source, start=(0, 30), end=(100, 30)) is None
        if isinstance(source, Box):
            corner = stage.physics.shape_cast(source, start=(0, 8), end=(100, 8))
            assert corner is not None and corner.distance == pytest.approx(41)
            assert corner.normal == pytest.approx((-0.8, 0.6))
            assert corner.point == pytest.approx((46, 3))
    finally:
        close(stage)


def test_orientation_scale_and_offset() -> None:
    """Collider orientation is independent of travel heading; centers scale too."""
    stage = Stage(physics=True)
    wall = Sprite(Image.rectangle(2, 100), x=51, body_type=BodyType.STATIC)
    stage.add(wall)
    try:
        rotated = stage.physics.shape_cast(
            Box(10, 20), start=(0, 0), end=(100, 0), direction=0, scale=2
        )
        assert rotated is not None and rotated.distance == pytest.approx(30)
        offset = stage.physics.shape_cast(Circle(5, center=(3, 0)), start=(0, 0), end=(100, 0))
        assert offset is not None and offset.distance == pytest.approx(42)
    finally:
        close(stage)


def test_ignore_objects_predicate_sensors_and_ties() -> None:
    """Filtering is per owner, stable under ties, and never changes actual collisions."""
    stage = Stage(physics=True)
    sensor = Sprite(Image.rectangle(10, 10), x=20, body_type=BodyType.STATIC)
    first = Sprite(sensor.image, x=50, body_type=BodyType.STATIC)
    second = Sprite(sensor.image, x=50, body_type=BodyType.STATIC)
    for actor in (sensor, first, second):
        stage.add(actor)
    sensor.body.sensor = True
    calls: list[CastTarget] = []

    def ignore(target: CastTarget) -> bool:
        calls.append(target)
        return target is first

    try:
        hit = stage.physics.raycast((0, 0), (100, 0))
        assert hit is not None and hit.target is first
        hit = stage.physics.raycast((0, 0), (100, 0), ignore=(first,))
        assert hit is not None and hit.target is second
        hit = stage.physics.raycast((0, 0), (100, 0), ignore=ignore)
        assert hit is not None and hit.target is second and calls == [first, second]
        assert stage.physics.raycast((0, 0), (100, 0), ignore=(first, second)) is None
        assert not first.body.sensor and sensor.body.sensor
    finally:
        close(stage)


def test_initial_overlap_zero_length_and_contact_directions() -> None:
    """Inside rays report zero; touching movement can separate or slide along a wall."""
    stage = Stage(physics=True)
    wall = Sprite(Image.rectangle(10, 100), x=15, body_type=BodyType.STATIC)
    stage.add(wall)
    try:
        inside = stage.physics.raycast((15, 0), (15, 0))
        assert inside is not None and inside.distance == 0 and inside.normal == (0, 0)
        assert stage.physics.raycast((0, 0), (0, 0)) is None
        assert stage.physics.shape_cast(Box(10, 10), start=(5, 0), end=(0, 0)) is None
        assert stage.physics.shape_cast(Box(10, 10), start=(5, 0), end=(5, 20)) is None
        into = stage.physics.shape_cast(Box(10, 10), start=(5, 0), end=(8, 0))
        assert into is not None and into.distance == 0
        overlap = stage.physics.shape_cast(Box(10, 10), start=(15, 0), end=(15, 0))
        assert overlap is not None and overlap.distance == 0
    finally:
        close(stage)


def test_one_way_direction_and_hit_snapshot() -> None:
    """Movement passes upward through one-way cells; ray hits remain geometric snapshots."""
    stage = Stage(physics=True)
    grid = TileMap(
        ["P"], {"P": Image.rectangle(40, 10)}, tile_size=(40, 10), one_way={"P"}, x=-20, y=0
    )
    stage.add(grid)
    try:
        assert stage.physics.shape_cast(Box(10, 10), start=(0, -20), end=(0, 20)) is None
        down = stage.physics.shape_cast(Box(10, 10), start=(0, 20), end=(0, -20))
        assert down is not None and down.distance == pytest.approx(15) and down.cell == (0, 0)
        assert down.normal == pytest.approx((0, 1))
        up = stage.physics.raycast((0, -20), (0, 20))
        assert up is not None and up.cell == (0, 0)
        grid.set_tile(row=0, column=0, tile=None)
        assert down.point == pytest.approx((0, 0)) and down.target is grid
        assert stage.physics.raycast((0, -20), (0, 20)) is None
    finally:
        close(stage)


def test_resting_body_can_travel_horizontally() -> None:
    """Solver-floor penetration must not make an enemy see a wall in front of itself."""
    from plocks._physics import _integrate

    stage = Stage(physics=True)
    actor = Sprite(Image.rectangle(10, 10), y=10)
    floor = Sprite(Image.rectangle(300, 10), y=-5, body_type=BodyType.STATIC)
    stage.add(actor)
    stage.add(floor)
    actor.body.rotation_locked = True
    try:
        for _ in range(90):
            _integrate(stage, 1 / 60)
        assert actor.body.grounded
        assert actor.body.can_travel(distance=20, direction=90)
        assert not actor.body.can_travel(distance=20, direction=180)
    finally:
        close(stage)


def test_filters_fail_without_mutation_and_slots_match_approval() -> None:
    """Callback errors are observed; results add no owners or mutable lifecycle facts."""
    from dataclasses import FrozenInstanceError, fields
    from typing import cast

    stage = Stage(physics=True)
    target = Sprite(Image.rectangle(10, 10), x=50, body_type=BodyType.STATIC)
    stage.add(target)
    before = target.position, target.body.velocity, tuple(stage.objects)

    def fail(owner: CastTarget) -> bool:
        raise ArithmeticError("ignore failure")

    def wrong(owner: CastTarget) -> str:
        return "yes"

    async def asynchronous(owner: CastTarget) -> bool:
        return True

    try:
        with pytest.raises(ArithmeticError, match="ignore failure"):
            stage.physics.raycast((0, 0), (100, 0), ignore=fail)
        with pytest.raises(TypeError, match="bool"):
            stage.physics.raycast((0, 0), (100, 0), ignore=cast(CastIgnore, wrong))
        with pytest.raises(TypeError, match="synchronous"):
            stage.physics.raycast((0, 0), (100, 0), ignore=cast(CastIgnore, asynchronous))
        hit = stage.physics.raycast((0, 0), (100, 0))
        assert hit is not None
        assert {f.name for f in fields(hit)} == {"target", "point", "normal", "distance", "cell"}
        with pytest.raises(FrozenInstanceError):
            field_name = "distance"
            setattr(hit, field_name, 1)
        assert before == (target.position, target.body.velocity, tuple(stage.objects))
        with pytest.raises(ValueError):
            target.body.can_travel(distance=-1)
        with pytest.raises(ValueError):
            stage.physics.raycast((0, 0), (float("inf"), 0))
        with pytest.raises(ValueError):
            stage.physics.shape_cast(Box(1, 1), start=(0, 0), end=(1, 0), scale=0)
        saved = target.body
        target.remove()
        with pytest.raises(PhysicsError):
            saved.can_travel(distance=1)
    finally:
        close(stage)


def test_tile_filter_once_visibility_and_cell_edits() -> None:
    """One map is one filter owner even when a sweep crosses several physical cells."""
    stage = Stage(physics=True)
    grid = TileMap(
        ["###"], {"#": Image.rectangle(10, 20)}, tile_size=(10, 20), solid={"#"}, x=50, y=10
    )
    grid.visible = False
    stage.add(grid)
    calls: list[CastTarget] = []

    def keep(target: CastTarget) -> bool:
        calls.append(target)
        return False

    try:
        hit = stage.physics.shape_cast(Circle(2), start=(0, 0), end=(100, 0), ignore=keep)
        assert hit is not None and hit.cell == (0, 0)
        assert calls == [grid]
        assert stage.physics.raycast((0, 0), (100, 0), ignore=(grid,)) is None
        grid.set_tile(row=0, column=0, tile=None)
        next_hit = stage.physics.raycast((0, 0), (100, 0))
        assert next_hit is not None and next_hit.cell == (0, 1) and next_hit.distance == 60
        assert hit.cell == (0, 0) and hit.distance == 48
        stage._state = "running"
        stage.pause()
        assert stage.physics.raycast((0, 0), (100, 0)) is not None
    finally:
        close(stage)
    with pytest.raises(PhysicsError):
        stage.physics.raycast((0, 0), (100, 0))


def test_body_cast_borrows_actual_one_way_collider() -> None:
    """A one-way actor casts its physical top edge, not its visual enclosing box."""
    stage = Stage(physics=True)
    platform = Sprite(Image.rectangle(40, 20), body_type=BodyType.KINEMATIC, one_way=True)
    obstacle = Sprite(Image.rectangle(10, 10), x=60, y=-5, body_type=BodyType.STATIC)
    stage.add(platform)
    stage.add(obstacle)
    try:
        assert platform.body.can_travel(distance=100, direction=90)
        obstacle.y = 10
        hit = platform.body.shape_cast(distance=100, direction=90)
        assert hit is not None and hit.target is obstacle and hit.distance == pytest.approx(35)
    finally:
        close(stage)


def test_one_way_cell_identity_with_fractional_world_origin() -> None:
    """Cell coordinates do not drift to an adjacent row at a one-way top edge."""
    stage = Stage(physics=True)
    grid = TileMap(
        [".", "P"], {"P": Image.rectangle(32, 32)}, tile_size=(32, 32), one_way={"P"}, x=0.1, y=0.3
    )
    stage.add(grid)
    try:
        hit = stage.physics.raycast((16.1, 10), (16.1, -100))
        assert hit is not None and hit.cell == (1, 0)
    finally:
        close(stage)


def test_box_face_hits_rotated_target_at_its_vertex() -> None:
    """The hit point lies on the contact feature, not a nearby non-contact face."""
    from math import sqrt

    stage = Stage(physics=True)
    target = Sprite(Image.rectangle(20, 20), x=50, body_type=BodyType.STATIC)
    target.direction = 135
    stage.add(target)
    try:
        hit = stage.physics.shape_cast(Box(10, 20), start=(0, 8), end=(100, 8))
        assert hit is not None
        assert hit.distance == pytest.approx(45 - 10 * sqrt(2))
        assert hit.point == pytest.approx((50 - 10 * sqrt(2), 0), abs=1e-7)
    finally:
        close(stage)
