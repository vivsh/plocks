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
