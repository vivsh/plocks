"""Point/bounds geometry and explicit directional world velocity."""

import pytest

from plocks import BodyType, Bounds, Image, PhysicsError, Puppet, Sprite, Stage, distance
from plocks._runtime import close


def test_point_actor_and_bounds_distances() -> None:
    first = Sprite(Image.rectangle(10, 10), x=1, y=2)
    second = Puppet.stick_figure()
    second.position = (4, 6)
    assert distance((1, 2), (4, 6)) == 5
    assert first.distance_to(second) == second.distance_to(first) == 5
    assert first.distance_to((4, 6)) == 5
    a = Bounds(0, 0, 10, 10)
    assert a.distance_to(Bounds(13, 14, 20, 20)) == 5
    assert a.distance_to(Bounds(10, 0, 20, 10)) == 0
    assert a.distance_to(Bounds(5, 5, 15, 15)) == 0
    with pytest.raises(ValueError):
        distance((float("nan"), 0), (0, 0))


@pytest.mark.parametrize(
    "direction, expected",
    [(0, (0, 100)), (90, (100, 0)), (180, (0, -100)), (270, (-100, 0)), (450, (100, 0))],
)
def test_travel_along_sets_velocity_once(direction: float, expected: tuple[int, int]) -> None:
    stage = Stage(physics=True)
    actor = Sprite(Image.rectangle(10, 10))
    stage.add(actor)
    try:
        actor.body.travel_along(speed=100, direction=direction)
        assert actor.body.velocity == pytest.approx(expected)
        actor.direction = 90
        assert actor.body.velocity == pytest.approx(expected)
        actor.direction = 270
        actor.body.travel_along(speed=100)
        assert actor.body.velocity == pytest.approx((-100, 0))
        actor.body.travel_along(speed=0)
        assert actor.body.velocity == (0, 0)
        with pytest.raises(ValueError):
            actor.body.travel_along(speed=-1)
        assert actor.body.velocity == (0, 0)
    finally:
        close(stage)
    with pytest.raises(PhysicsError):
        actor.body.travel_along(speed=100)


def test_static_travel_rejects_before_mutation() -> None:
    stage = Stage(physics=True)
    actor = Sprite(Image.rectangle(10, 10), body_type=BodyType.STATIC)
    stage.add(actor)
    try:
        with pytest.raises(PhysicsError):
            actor.body.travel_along(speed=100)
        assert actor.body.velocity == (0, 0)
    finally:
        close(stage)


@pytest.mark.parametrize("puppet", [False, True])
@pytest.mark.parametrize(
    "point, expected",
    [
        ((10, 30), 0),
        ((20, 30), 45),
        ((20, 20), 90),
        ((20, 10), 135),
        ((10, 10), 180),
        ((0, 10), 225),
        ((0, 20), 270),
        ((0, 30), 315),
    ],
)
def test_direction_to_points(puppet: bool, point: tuple[int, int], expected: int) -> None:
    """Both detached actors measure clockwise world headings from their anchors."""
    actor = Puppet.stick_figure() if puppet else Sprite(Image.rectangle(10, 10))
    actor.position = (10, 20)
    actor.direction = 123
    assert actor.direction_to(point) == pytest.approx(expected)
    assert actor.position == (10, 20) and actor.direction == 123


@pytest.mark.parametrize("source_puppet", [False, True])
@pytest.mark.parametrize("target_puppet", [False, True])
def test_direction_to_actors_and_coincidence(source_puppet: bool, target_puppet: bool) -> None:
    """Sprite/Puppet targets are sampled afresh; coincidence preserves the source facing."""
    from plocks.motion import _point_towards

    actor = Puppet.stick_figure() if source_puppet else Sprite(Image.rectangle(10, 10))
    target = Puppet.stick_figure() if target_puppet else Sprite(Image.rectangle(10, 10))
    actor.direction = 234
    assert actor.direction_to(target) == 234
    assert actor.direction_to(actor.position) == 234
    target.position = (-50, 50)
    assert actor.direction_to(target) == 315
    assert target.direction == 90
    _point_towards(actor, target)
    assert actor.direction == 315
    target.position = (50, -50)
    assert actor.direction_to(target) == 135
    assert actor.direction == 315


@pytest.mark.parametrize("puppet", [False, True])
@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_direction_to_rejects_nonfinite_coordinates(puppet: bool, invalid: float) -> None:
    """Invalid targets fail before changing the querying actor."""
    actor = Puppet.stick_figure() if puppet else Sprite(Image.rectangle(10, 10))
    with pytest.raises(ValueError):
        actor.direction_to((invalid, 0))
    with pytest.raises(ValueError):
        actor.direction_to((0, invalid))
    assert actor.position == (0, 0) and actor.direction == 90


def test_direction_to_physical_actor_is_read_only() -> None:
    """Camera, visibility and visual rotation do not change heading or body velocity."""
    from plocks import RotationStyle

    stage = Stage(physics=True)
    actor = Sprite(Image.rectangle(10, 20), direction=270)
    target = Puppet.stick_figure()
    target.position = (100, 0)
    stage.add(actor)
    stage.add(target)
    try:
        stage.camera = (30, 40)
        actor.rotation_style = RotationStyle.NONE
        target.visible = False
        actor.body.velocity = (20, 30)
        assert actor.direction_to(target) == 90
        assert actor.direction == 270
        assert actor.position == (0, 0)
        assert actor.body.velocity == (20, 30)
        actor.body.travel_along(speed=120, direction=actor.direction_to(target))
        assert actor.body.velocity == pytest.approx((120, 0))
    finally:
        close(stage)
