"""Automatic shape sizing and nonmutating clearance queries."""

import pytest

from plocks import Anchor, Body, BodyType, Box, Circle, Image, PhysicsError, Sprite, Stage
from plocks._physics import _integrate
from plocks._runtime import close


def box_width(body: Body) -> float:
    shape = body.shape
    assert isinstance(shape, Box)
    return shape.width


def test_grounded_crouch_and_ceiling() -> None:
    stage = Stage(physics=True)
    standing = Image.rectangle(24, 40, color="red").with_anchor(Anchor.BOTTOM_CENTER)
    crouching = Image.rectangle(24, 20, color="red").with_anchor(Anchor.BOTTOM_CENTER)
    hero = Sprite(standing, y=0)
    floor = Sprite(Image.rectangle(200, 10, color="white"), y=-5, body_type=BodyType.STATIC)
    ceiling = Sprite(Image.rectangle(80, 10, color="white"), y=35, body_type=BodyType.STATIC)
    stage.add(floor)
    stage.add(hero)
    hero.body.rotation_locked = True
    try:
        for _ in range(60):
            _integrate(stage, 1 / 60)
        feet = hero.y
        hero.image = crouching
        assert hero.body.shape == Box(24, 20, (0, 10))
        assert hero.y == feet
        stage.add(ceiling)
        assert not hero.body.can_fit_image(standing)
        assert hero.body.can_fit_image(crouching)
        stage.remove(ceiling)
        assert hero.body.can_fit_image(standing)
        hero.image = standing
        assert hero.body.shape == Box(24, 40, (0, 20))
        for _ in range(30):
            _integrate(stage, 1 / 60)
        assert hero.y == pytest.approx(feet, abs=0.2)
    finally:
        close(stage)


def test_custom_shape_mode_and_retirement() -> None:
    stage = Stage(physics=True)
    actor = Sprite(Image.rectangle(20, 40))
    stage.add(actor)
    body = actor.body
    try:
        body.shape = Circle(8)
        assert not body.auto_shape
        actor.image = Image.rectangle(40, 10)
        assert body.shape == Circle(8)
        body.use_actor_shape()
        assert body.auto_shape and body.shape == Box(40, 10)
        body.mass = 3
        body.velocity = (30, 40)
        body.drag = (2, 3)
        body.friction = 0.2
        body.bounce = 0.4
        actor.image = Image.rectangle(12, 20)
        assert body.mass == 3 and body.velocity == (30, 40)
        assert body.drag == (2, 3) and body.friction == 0.2 and body.bounce == 0.4
        stage.remove(actor)
        with pytest.raises(PhysicsError):
            body.can_fit_shape(Box(1, 1))
        stage.add(actor)
        assert actor.body.auto_shape
    finally:
        close(stage)


@pytest.mark.parametrize("role", [BodyType.STATIC, BodyType.KINEMATIC, BodyType.DYNAMIC])
def test_clearance_edges_sensors_and_no_mutation(role: BodyType) -> None:
    stage = Stage(physics=True)
    actor = Sprite(Image.rectangle(10, 10))
    obstacle = Sprite(Image.rectangle(10, 10), x=15, body_type=role)
    stage.add(actor)
    stage.add(obstacle)
    try:
        original = actor.body.shape
        assert actor.body.can_fit_shape(Box(20, 10))  # Exact edge contact.
        assert not actor.body.can_fit_shape(Box(22, 10))
        obstacle.body.sensor = True
        assert actor.body.can_fit_shape(Box(22, 10))
        assert actor.body.shape == original and actor.body.auto_shape
        native = actor.body._native
        assert native is not None and len(native.shapes) == 1
    finally:
        close(stage)


def test_animation_samples_same_sized_frames_without_replacement() -> None:
    from plocks._scripts import _sample, _step

    stage = Stage(physics=True)
    actor = Sprite(Image.rectangle(10, 10))
    stage.add(actor)
    stage._state = "running"
    try:
        actor.images((Image.rectangle(10, 10), Image.rectangle(10, 30)), fps=2)
        _step(stage)
        native = actor.body._native
        assert native is not None
        first = tuple(native.shapes)
        _sample(stage)
        assert tuple(native.shapes) == first
        stage._tick = 30
        _sample(stage)
        assert actor.body.shape == Box(10, 30)
        actor.stop()
        assert actor.body.shape == Box(10, 30)
    finally:
        close(stage)


def test_puppet_pose_parts_and_fixed_mode() -> None:
    from plocks import Joint, Puppet, Skeleton
    from plocks._scripts import _sample, _step

    stage = Stage(physics=True)
    skeleton = Skeleton({"root": Joint(None)})
    actor = Puppet(skeleton, parts={"root": Image.rectangle(10, 30)})
    stage.add(actor)
    stage._state = "running"
    rest = skeleton.rest_pose()
    bent = rest.with_angles({"root": 90})
    try:
        actor.pose = bent
        assert box_width(actor.body) == pytest.approx(30)
        assert actor.body.can_fit_pose(rest)
        actor.poses((rest, bent), fps=1)
        _step(stage)
        stage._tick = 30
        _sample(stage)
        assert box_width(actor.body) == pytest.approx(40 / 2**0.5)
        actor.body.shape = Circle(5)
        stage._tick = 60
        _sample(stage)
        assert actor.body.shape == Circle(5)
        actor.body.use_actor_shape()
        assert box_width(actor.body) == pytest.approx(30)
        with pytest.raises(PhysicsError):
            actor.body.can_fit_image(Image.rectangle(1, 1))
        with pytest.raises(ValueError):
            actor.body.can_fit_pose(Skeleton({"root": Joint(None)}).rest_pose())
        actor.set_part_image("root", Image.rectangle(10, 50))
        _step(stage)
        assert box_width(actor.body) == pytest.approx(50)
    finally:
        close(stage)


def test_one_way_queries_and_clones() -> None:
    stage = Stage(physics=True)
    hero = Sprite(Image.rectangle(10, 10), y=10)
    platform = Sprite(Image.rectangle(100, 10), body_type=BodyType.STATIC, one_way=True)
    stage.add(hero)
    stage.add(platform)
    try:
        assert hero.body.can_fit_shape(Box(10, 10))
        assert not hero.body.can_fit_shape(Box(10, 30))
        hero.y = -20
        assert hero.body.can_fit_shape(Box(10, 60))  # Underneath is pass-through.
        clone = hero.clone()
        assert clone.body.auto_shape
        hero.body.shape = Circle(4)
        fixed = hero.clone()
        assert not fixed.body.auto_shape and fixed.body.shape == Circle(4)
    finally:
        close(stage)


def test_scaled_rotated_tile_clearance_and_invalid_update() -> None:
    from plocks import TileMap

    stage = Stage(physics=True)
    actor = Sprite(Image.rectangle(10, 10), x=20, y=20)
    stage.add(actor)
    tiles = TileMap(
        ["#"], {"#": Image.rectangle(10, 10)}, tile_size=(10, 10), solid={"#"}, x=30, y=25
    )
    stage.add(tiles)
    try:
        assert actor.body.can_fit_shape(Box(10, 10))
        actor.scale = 2
        assert actor.body.can_fit_shape(Box(10, 10))  # Touches x=30.
        assert not actor.body.can_fit_shape(Box(12, 10))
        actor.direction = 0
        assert not actor.body.can_fit_shape(Box(10, 12))
        before = actor.body.shape
        with pytest.raises(ValueError):
            actor.body.shape = Box(-1, 2)
        assert actor.body.auto_shape and actor.body.shape == before
        clone = actor.clone()
        clone.image = Image.rectangle(5, 20)
        assert clone.body.shape == Box(5, 20) and actor.body.shape == before
    finally:
        close(stage)


def test_replacement_failure_preserves_mode_and_visual() -> None:
    from unittest.mock import patch

    stage = Stage(physics=True)
    original = Image.rectangle(10, 20)
    actor = Sprite(original)
    stage.add(actor)
    try:
        body = actor.body
        shape = body.shape
        with patch("plocks._physics._shape", side_effect=ArithmeticError("native failure")):
            with pytest.raises(ArithmeticError):
                actor.image = Image.rectangle(20, 10)
            assert actor.image is original and body.shape is shape and body.auto_shape
            with pytest.raises(ArithmeticError):
                body.shape = Circle(5)
            assert body.shape is shape and body.auto_shape
        body.shape = Circle(5)
        with patch("plocks._physics._shape", side_effect=ArithmeticError("native failure")):
            with pytest.raises(ArithmeticError):
                body.use_actor_shape()
            assert body.shape == Circle(5) and not body.auto_shape
    finally:
        close(stage)
