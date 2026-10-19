"""Physical links own native resources, units and dependency lifetimes exactly once."""

from collections.abc import Iterator
from math import degrees
from pathlib import Path
from unittest.mock import patch

import pymunk
import pytest

from plocks import (
    BodyType,
    Box,
    Event,
    Hinge,
    PhysicsError,
    Rope,
    Sprite,
    Stage,
)
from plocks._connections import _anchors
from plocks._runtime import advance, close

IMAGE = Path(__file__).parent / "fixtures/games/state_proof/assets/hero.png"


@pytest.fixture
def stage() -> Iterator[Stage]:
    """A zero-gravity world makes independent mechanical behavior measurable."""
    world = Stage(physics=True)
    world.physics.gravity = (0, 0)
    world._state = "running"
    world._last_wall = 0
    yield world
    close(world)
    assert not world.physics._connections and not world.physics._bodies


def actor(stage: Stage, *, x: float = 100, y: float = 0) -> Sprite:
    """A static image with a small explicit collision shape and free rotation."""
    result = Sprite(IMAGE, x=x, y=y)
    stage.add(result)
    result.body.shape = Box(10, 20)
    return result


def ticks(stage: Stage, count: int = 1) -> None:
    """Advance normal actions and bounded native stepping together."""
    for _ in range(count):
        advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)


def test_rope_captures_length_can_go_slack_and_releases_without_removing_actor(
    stage: Stage,
) -> None:
    """Maximum-distance links never push slack ends apart and retire idempotently."""
    ball = actor(stage)
    link = stage.physics.rope((0, 0), ball)
    assert link.length == 100 and link.a == (0, 0) and link.b is ball
    link.length = 150
    ticks(stage, 10)
    assert ball.x == pytest.approx(100)
    ball.body.impulse(x=-10)
    ticks(stage, 10)
    assert ball.x < 100
    link.disconnect()
    link.disconnect()
    assert not link.connected and ball in stage.objects
    with pytest.raises(PhysicsError):
        _ = link.length
    with pytest.raises(TypeError):
        Rope()
    assert not hasattr(link, "__dict__")


def test_spring_settles_and_owns_its_native_configuration(stage: Stage) -> None:
    """Damped spring properties are read directly from the live native resource."""
    ball = actor(stage)
    spring = stage.physics.spring((0, 0), ball, rest_length=50, stiffness=100, damping=10)
    assert spring.rest_length == 50 and spring.stiffness == 100 and spring.damping == 10
    ticks(stage, 180)
    assert ball.x == pytest.approx(50, abs=0.1) and abs(ball.body.velocity[0]) < 0.1
    old = spring.stiffness
    with pytest.raises(ValueError):
        spring.stiffness = float("nan")
    assert spring.stiffness == old
    spring.rest_length = 60
    spring.damping = 20
    ticks(stage, 180)
    assert ball.x == pytest.approx(60, abs=0.1)


def test_hinge_motor_clockwise_units_limits_and_dependency_teardown(stage: Stage) -> None:
    """Motor speed uses Plocks degrees, stops at hinge limits and cannot outlive them."""
    arm = actor(stage, x=0, y=30)
    arm.body.shape = Box(10, 60)
    hinge = stage.physics.hinge((0, 0), arm, anchor_b=(0, -30), limits=(-30, 30))
    motor = hinge.motor(speed=60, max_torque=10000)
    assert motor.speed == pytest.approx(60) and motor.max_torque == 10000
    ticks(stage, 120)
    pivot = hinge._native[0]
    angle = -degrees(pivot.b.angle - pivot.a.angle)
    assert 29 <= angle <= 31
    assert not hinge.collide and not motor.collide
    motor.collide = True
    assert hinge.collide and motor.collide and motor._native[0].collide_bodies
    motor.speed = -60
    ticks(stage, 120)
    angle = -degrees(pivot.b.angle - pivot.a.angle)
    assert -31 <= angle <= -29
    with pytest.raises(PhysicsError, match="already"):
        hinge.motor(speed=30, max_torque=100)
    with pytest.raises(PhysicsError, match="locking"):
        arm.body.rotation_locked = True
    assert not arm.body.rotation_locked
    hinge.disconnect()
    assert not hinge.connected and not motor.connected and not stage.physics._connections
    with pytest.raises(PhysicsError):
        motor.speed = 0
    arm.body.rotation_locked = True


def test_replacing_and_scaling_preserve_local_anchors_and_native_link(stage: Stage) -> None:
    """Anchor scaling uses operation-local old/new values, not cached actor transforms."""
    ball = actor(stage)
    rope = stage.physics.rope((0, 0), ball, anchor_b=(10, 0))
    native = rope._native[0]
    assert _anchors(rope)[1] == (110, 0)
    ball.scale = 2
    assert rope._native[0] is native and rope.length == 110
    assert _anchors(rope)[1] == (120, 0)
    ball.body.shape = Box(12, 12)
    assert _anchors(rope)[1] == (120, 0)
    ball.direction = 180
    assert _anchors(rope)[1] == pytest.approx((100, -20))


def test_removal_and_clone_do_not_reconnect_to_the_original_network(stage: Stage) -> None:
    """Individual clones have independent bodies; endpoint removal retires incident links."""
    first, second = actor(stage, x=0), actor(stage, x=30)
    hinge = stage.physics.hinge(first, second, anchor_a=(15, 0), anchor_b=(-15, 0))
    motor = hinge.motor(speed=30, max_torque=1000)
    clone = first.clone()
    assert len(stage.physics._connections) == 2
    assert all(
        clone is not endpoint for link in stage.physics._connections for endpoint in link._endpoints
    )
    stage.remove(first)
    assert not hinge.connected and not motor.connected and clone in stage.objects
    stage.add(first)
    assert not stage.physics._connections


@pytest.mark.parametrize("kind", ["rope", "hinge", "spring"])
def test_factory_errors_leave_no_native_or_python_resource(kind: str, stage: Stage) -> None:
    """Endpoint and input validation precede admission to either owner."""
    ball = actor(stage)
    before = tuple(stage.physics._space.constraints) if stage.physics._space is not None else ()
    with pytest.raises(PhysicsError):
        if kind == "rope":
            stage.physics.rope(ball, ball)
        elif kind == "hinge":
            stage.physics.hinge(ball, ball)
        else:
            stage.physics.spring(ball, ball)
    assert not stage.physics._connections
    assert stage.physics._space is not None and tuple(stage.physics._space.constraints) == before
    with pytest.raises(ValueError):
        stage.physics.rope((0, 0), ball, anchor_a=(1, 0))
    with pytest.raises(ValueError):
        stage.physics.hinge((0, 0), ball, limits=(10, 20))
    with pytest.raises(ValueError):
        stage.physics.spring((0, 0), ball, stiffness=0)


def test_partial_native_hinge_attachment_rolls_back_original_exception(stage: Stage) -> None:
    """A failed multi-constraint admission removes its already-added pivot only."""
    ball = actor(stage)
    space = stage.physics._space
    assert space is not None
    original = space.add
    failure = RuntimeError("second constraint failed")

    def partial(*objects: pymunk.Body | pymunk.Shape | pymunk.Constraint) -> None:
        original(objects[0])
        raise failure

    with patch.object(space, "add", partial), pytest.raises(RuntimeError) as captured:
        stage.physics.hinge((100, 0), ball, limits=(-30, 30))
    assert captured.value is failure and not space.constraints and not stage.physics._connections
    assert len(stage.physics._bodies) == 1


def test_pause_and_bounded_stiffness_use_existing_simulation(stage: Stage) -> None:
    """Pause freezes connected motion, while unsafe workloads fail before native stepping."""
    ball = actor(stage)
    spring = stage.physics.spring((0, 0), ball, rest_length=50)
    stage.pause()
    ticks(stage, 30)
    assert ball.x == 100
    stage.resume()
    ticks(stage, 3)
    assert ball.x < 100
    spring.stiffness = 1e300
    with pytest.raises(PhysicsError, match="substeps|stiffness"):
        ticks(stage)


def test_actor_removal_from_an_update_releases_connections_before_native_body() -> None:
    """User callbacks can remove a connected actor without leaving solver references."""
    stage = Stage(physics=True)
    ball = actor(stage)
    link = stage.physics.rope((0, 0), ball)

    @stage.on_update
    def remove(event: Event[Stage, float]) -> None:
        stage.remove(ball)
        assert not link.connected
        stage.stop()

    stage.run()
    assert not stage.physics._connections and not stage.physics._bodies


def test_wheeled_cart_rolls_and_chain_hinges_stay_connected(stage: Stage) -> None:
    """The same primitives support a driven vehicle and a multi-link hanging assembly."""
    from plocks import Circle

    stage.physics.gravity = (0, -600)
    floor = Sprite(IMAGE, y=-30, body_type=BodyType.STATIC)
    stage.add(floor)
    floor.body.shape = Box(1000, 20)
    chassis = actor(stage, x=0, y=30)
    chassis.body.shape = Box(80, 16)
    wheels: list[Sprite] = []
    for x in (-25, 25):
        wheel = actor(stage, x=x, y=0)
        wheel.body.shape = Circle(15)
        wheel.body.friction = 1
        hinge = stage.physics.hinge(chassis, wheel, anchor_a=(x, -30))
        hinge.motor(speed=180, max_torque=10000)
        wheels.append(wheel)
    previous: Sprite | None = None
    chain: list[Hinge] = []
    for index in range(6):
        link = actor(stage, x=-200 + index * 20, y=150)
        link.body.shape = Box(20, 6)
        if previous is None:
            chain.append(stage.physics.hinge((-210, 150), link, anchor_b=(-10, 0)))
        else:
            chain.append(stage.physics.hinge(previous, link, anchor_a=(10, 0), anchor_b=(-10, 0)))
        previous = link
    ticks(stage, 120)
    assert chassis.x > 30 and all(link.connected for link in chain)
    for hinge in chain:
        a, b = _anchors(hinge)
        assert abs(a[0] - b[0]) < 1 and abs(a[1] - b[1]) < 1


def test_connection_budget_and_cross_stage_validation_precede_allocation(stage: Stage) -> None:
    """The resource cap counts native constraints; invalid endpoints allocate no link."""
    ball = actor(stage)
    other = Stage(physics=True)
    foreign = actor(other)
    try:
        with pytest.raises(PhysicsError, match="stage"):
            stage.physics.rope(ball, foreign)
        with pytest.raises(PhysicsError, match="distinct"):
            stage.physics.rope((0, 0), (10, 0))
        for _ in range(512):
            stage.physics.hinge((100, 0), ball, limits=(0, 0))
        assert stage.physics._space is not None
        assert len(stage.physics._space.constraints) == 1024
        with pytest.raises(PhysicsError, match="1024"):
            stage.physics.rope((0, 0), ball)
        assert len(stage.physics._connections) == 512
    finally:
        close(other)


def test_shape_failure_restores_local_anchors_and_retains_original_scale(stage: Stage) -> None:
    """Failed collider removal restores both native attachment geometry and membership."""
    ball = actor(stage)
    rope = stage.physics.rope((0, 0), ball, anchor_b=(10, 0))
    before = _anchors(rope)
    space = stage.physics._space
    assert space is not None
    original = space.remove
    failure = RuntimeError("shape removal failed")
    raised = False

    def remove(*items: pymunk.Body | pymunk.Shape | pymunk.Constraint) -> None:
        nonlocal raised
        if not raised:
            raised = True
            raise failure
        original(*items)

    with patch.object(space, "remove", remove), pytest.raises(RuntimeError) as captured:
        ball.scale = 2
    assert captured.value is failure and ball.scale == 1
    assert _anchors(rope) == before and rope.connected
    assert len(space.shapes) == 1
    ticks(stage)


def test_failure_after_motor_creation_retires_all_links_before_bodies() -> None:
    """A normal game exception cannot leave dependent native motor resources alive."""
    stage = Stage(physics=True)
    arm = actor(stage)
    hinge = stage.physics.hinge((100, 0), arm)
    motor = hinge.motor(speed=0, max_torque=100)
    failure = RuntimeError("assembly failed")

    @stage.on_update
    def fail(event: Event[Stage, float]) -> None:
        raise failure

    with pytest.raises(RuntimeError) as captured:
        stage.run()
    assert captured.value is failure and not hinge.connected and not motor.connected
    assert not stage.physics._connections and not stage.physics._bodies
