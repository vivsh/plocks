"""Clones use the same world with independent native bodies, shapes and contacts."""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from plocks import (
    Actor,
    BodyType,
    Box,
    Circle,
    Event,
    Joint,
    PhysicsError,
    Puppet,
    Script,
    Skeleton,
    Sprite,
    Stage,
)
from plocks._physics import _space
from plocks._runtime import close
from tests.test_clones import ticks

IMAGE = Path(__file__).parent / "fixtures/games/state_proof/assets/hero.png"


@pytest.fixture
def physics() -> Iterator[Stage]:
    """Each physical world is owned and completely retired by its test."""
    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    yield stage
    close(stage)


@pytest.mark.parametrize("kind", ["sprite", "puppet"])
@pytest.mark.parametrize("role", list(BodyType))
def test_each_role_has_separate_native_resources_and_copied_configuration(
    physics: Stage, role: BodyType, kind: str
) -> None:
    """Every actor/role preserves placement and configuration without inheriting motion."""
    source: Actor
    if kind == "sprite":
        source = Sprite(IMAGE, body_type=role)
    else:
        source = Puppet(Skeleton({"root": Joint(None)}), parts={"root": IMAGE}, body_type=role)
    source.position, source.direction, source.scale = (-100, 80), 37, 1.75
    physics.add(source)
    if role is not BodyType.NONE:
        source.body.shape = Circle(6, center=(3, -2))
        source.body.friction, source.body.bounce = 0.23, 0.8
        if role is BodyType.DYNAMIC:
            source.body.mass = 3
            source.body.rotation_locked = True
            source.body.velocity = (24, 25)
        elif role is BodyType.KINEMATIC:
            source.body.velocity = (24, 25)
            source.body.angular_velocity = 120
    clone = source.clone()
    assert type(clone) is type(source)
    assert clone.position == pytest.approx(source.position)
    assert clone.direction == pytest.approx(source.direction)
    assert clone.scale == source.scale and clone.body_type is role
    if role is BodyType.NONE:
        with pytest.raises(PhysicsError):
            _ = clone.body
        assert not physics.physics._bodies
    else:
        before, after = source.body, clone.body
        assert before is not after and before._native is not after._native
        assert before._native is not None and after._native is not None
        assert next(iter(before._native.shapes)) is not next(iter(after._native.shapes))
        assert after.shape is before.shape
        assert after.friction == 0.23 and after.bounce == 0.8
        assert after.velocity == (0, 0) and after.angular_velocity == 0
        assert after._native.force == (0, 0) and after._native.torque == 0
        if role is BodyType.DYNAMIC:
            assert after.mass == 3 and after.rotation_locked
        physics.remove(clone)
        assert after._native is None and before._native is not None
        assert len(_space(physics.physics).bodies) == len(physics.physics._bodies) == 1


def test_impulse_force_and_torque_never_transfer_to_clone(physics: Stage) -> None:
    """Actions and accumulated motion belong to the original body's own execution."""
    source = Sprite(IMAGE, x=-100)
    physics.add(source)
    source.body.shape = Box(12, 20, center=(2, -3))
    source.body.mass = 2
    ticks(physics, 1)
    force = source.body.force(x=60, seconds=10)
    torque = source.body.torque(100, seconds=10)
    ticks(physics, 5)
    assert source.body.velocity[0] > 0 and source.body.angular_velocity > 0
    clone = source.clone()
    clone.position = (100, 0)
    assert clone.body.velocity == (0, 0) and clone.body.angular_velocity == 0
    assert len(physics._actions) == 2
    clone.body.impulse(x=40)
    ticks(physics, 1)
    assert clone.body.velocity[0] == pytest.approx(20)
    assert clone.body.angular_velocity == pytest.approx(0)
    assert not force.done and not torque.done
    physics.remove(source)
    assert force.cancelled and torque.cancelled
    velocity = clone.body.velocity
    ticks(physics, 10)
    assert clone.body.velocity == velocity and clone in physics.objects


def test_rotation_and_material_changes_are_independent(physics: Stage) -> None:
    """Copying a collider definition never shares mutable native shape or body properties."""
    source = Sprite(IMAGE, x=-100)
    physics.add(source)
    source.body.shape = Box(10, 20)
    source.body.mass = 2
    clone = source.clone()
    clone.position = (100, 0)
    clone.body.mass = 4
    clone.body.friction = 0.1
    clone.body.bounce = 0.9
    clone.body.shape = Circle(5)
    clone.body.angular_velocity = 90
    ticks(physics, 30)
    assert clone.direction == pytest.approx(135) and source.direction == 90
    assert source.body.mass == 2 and source.body.friction == 0.7 and source.body.bounce == 0
    assert isinstance(source.body.shape, Box) and isinstance(clone.body.shape, Circle)
    clone.body.rotation_locked = True
    direction = clone.direction
    ticks(physics, 10)
    assert clone.direction == direction and not source.body.rotation_locked


def test_kinematic_clone_does_not_copy_running_glide(physics: Stage) -> None:
    """A platform clone starts still while the original completes its admitted movement."""
    source = Sprite(IMAGE, x=-100, body_type=BodyType.KINEMATIC)
    physics.add(source)
    source.body.shape = Box(80, 10)
    source.body.friction = 0.2
    ticks(physics, 1)
    motion = source.glide_by(y=60, seconds=1)
    ticks(physics, 20)
    clone = source.clone()
    clone.x = 100
    height = clone.y
    assert clone.body.velocity == (0, 0)
    ticks(physics, 50)
    assert motion.done and source.y == pytest.approx(60)
    assert clone.y == pytest.approx(height) and clone.body.friction == 0.2


def test_clones_land_and_grounded_contacts_are_recomputed(physics: Stage) -> None:
    """New bodies start without source contacts, then land and jump independently."""
    physics.physics.gravity = (0, -500)
    floor = Sprite(IMAGE, y=-80, body_type=BodyType.STATIC)
    source = Sprite(IMAGE, x=-60, y=20)
    physics.add(floor)
    physics.add(source)
    floor.body.shape = Box(400, 10)
    source.body.shape = Circle(6)
    source.body.rotation_locked = True
    ticks(physics, 90)
    assert source.body.grounded
    clone = source.clone()
    clone.position = (60, 80)
    assert not clone.body.grounded
    ticks(physics, 90)
    assert source.body.grounded and clone.body.grounded
    assert clone.y == pytest.approx(-69, abs=0.5)
    source.body.impulse(y=300)
    ticks(physics, 10)
    assert not source.body.grounded and clone.body.grounded
    assert source.y > clone.y + 20
    physics.remove(source)
    ticks(physics, 10)
    assert clone.body.grounded and len(physics.physics._bodies) == 2


def test_clones_collide_with_each_other_without_hidden_exclusions(physics: Stage) -> None:
    """Independent clone shapes participate in ordinary rigid-body collision response."""
    source = Sprite(IMAGE, x=-25)
    physics.add(source)
    source.body.shape = Box(10, 10)
    source.body.friction, source.body.bounce = 0, 1
    clone = source.clone()
    clone.x = 25
    source.body.velocity, clone.body.velocity = (100, 0), (-100, 0)
    ticks(physics, 20)
    assert source.body.velocity[0] < 0 and clone.body.velocity[0] > 0
    assert source.x < clone.x


def test_removal_and_pausing_stop_only_the_appropriate_physics(physics: Stage) -> None:
    """Stage pause freezes both bodies; removing one clone invalidates only its own handle."""
    source = Sprite(IMAGE, x=-100)
    physics.add(source)
    clone = source.clone()
    clone.x = 100
    source.body.velocity, clone.body.velocity = (20, 0), (50, 0)
    ticks(physics, 10)
    physics.pause()
    points = (source.position, clone.position)
    ticks(physics, 30)
    assert points == (source.position, clone.position)
    physics.resume()
    ticks(physics, 5)
    assert source.x > points[0][0] and clone.x > points[1][0]
    stale = clone.body
    physics.remove(clone)
    with pytest.raises(PhysicsError):
        _ = stale.velocity
    start = source.x
    ticks(physics, 5)
    assert source.x > start
    close(physics)
    assert not physics.physics._bodies and physics.physics._space is None
    assert source._stage is clone._stage is None


def test_failed_physics_configuration_rolls_back_the_created_body(physics: Stage) -> None:
    """A failure after native attachment leaves only the original body and registrations."""
    source = Sprite(IMAGE)
    physics.add(source)
    source.on_clone(Script(Sprite).wait(1))
    native = source.body._native
    source.body.shape = source.body.shape  # Clone explicit fixed geometry.
    error = ArithmeticError("configuration failed")
    with (
        patch("plocks._physics._replace_shape", side_effect=error),
        pytest.raises(ArithmeticError) as caught,
    ):
        source.clone()
    assert caught.value is error
    assert physics.objects == (source,)
    assert len(physics.physics._bodies) == len(_space(physics.physics).bodies) == 1
    assert source.body._native is native
    assert len(physics._clone_handlers) == 1 and not physics._pending


def test_repeated_physics_clone_removal_releases_bodies_and_actions(physics: Stage) -> None:
    """Spawning physical copies repeatedly leaves no native shapes, runs or registrations."""
    source = Puppet.stick_figure()
    source.position = (-100, 0)
    physics.add(source)
    source.body.shape = Box(20, 80)
    source.body.mass = 3

    @source.on_clone
    def launch(event: Event[Puppet, None]) -> None:
        event.target.body.force(x=10, seconds=10)

    ticks(physics, 1)
    for _ in range(200):
        clone = source.clone()
        clone.position = (100, 0)
        ticks(physics, 1)
        body = clone.body
        physics.remove(clone)
        assert body._native is None
        assert len(physics.physics._bodies) == len(_space(physics.physics).bodies) == 1
        assert len(_space(physics.physics).shapes) == 1
        assert not physics._pending and not physics._actions and len(physics._clone_handlers) == 1


def test_failure_after_attachment_before_membership_retires_the_body(physics: Stage) -> None:
    """Even a partially attached body is removed when adding the clone fails."""
    from plocks._physics import _attach
    from plocks.physics import Physics

    source = Sprite(IMAGE)
    physics.add(source)

    def fail(world: Physics, actor: Actor) -> None:
        _attach(world, actor)
        raise OSError("attachment failure")

    with (
        patch("plocks._physics._attach", side_effect=fail),
        pytest.raises(OSError, match="attachment failure"),
    ):
        source.clone()
    assert physics.objects == (source,)
    assert len(physics.physics._bodies) == len(_space(physics.physics).bodies) == 1
    assert len(_space(physics.physics).shapes) == 1 and not physics._pending


def test_clones_use_the_existing_tile_terrain_and_follow_edits(physics: Stage) -> None:
    """Copied bodies land on shared terrain; removing their support affects only that actor."""
    from plocks import TileMap

    physics.physics.gravity = (0, -500)
    world = TileMap(["######"], {"#": IMAGE}, tile_size=(32, 32), solid={"#"}, x=-96, y=-80)
    physics.add(world)
    source = Sprite(IMAGE, x=-48, y=20)
    physics.add(source)
    source.body.shape = Circle(6)
    source.body.rotation_locked = True
    clone = source.clone()
    clone.position = (48, 40)
    ticks(physics, 90)
    assert source.body.grounded and clone.body.grounded
    assert source.body.touching(world) and clone.body.touching(world)
    world.set_tile(row=0, column=4, tile=None)
    ticks(physics, 30)
    assert source.body.grounded and not clone.body.grounded
    assert clone.y < source.y - 20
