"""The first integrated Body path has one native transform and deterministic retirement."""

import pytest
from PIL import Image as PillowImage

from plocks import (
    BodyType,
    Event,
    GamepadButton,
    GamepadPress,
    Key,
    PhysicsError,
    Sprite,
    Stage,
    TileMap,
)
from plocks._physics import _integrate
from plocks._runtime import close
from plocks._scripts import _sample, _step


def ticks(stage: Stage, count: int) -> None:
    for _ in range(count):
        _step(stage)
        _integrate(stage, 1 / stage.tick_rate)
        stage._tick += 1
        _sample(stage)


def test_fall_impulse_and_independent_recipe() -> None:
    stage = Stage(physics=True)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    hero = Sprite(PillowImage.new("RGBA", (20, 20)), y=20)
    friend = Sprite(hero.image, x=-100, y=80, body_type=BodyType.NONE)
    floor = TileMap(
        ["##########"], {"#": hero.image}, tile_size=(32, 32), solid={"#"}, x=-160, y=-100
    )
    stage.add(floor)
    stage.add(hero)
    stage.add(friend)
    stage._state = "running"
    hero.body.rotation_locked = True
    body = hero.body
    try:
        assert not body.grounded
        motion = friend.glide_by(x=100, seconds=1)
        ticks(stage, 90)
        assert body.grounded and hero.y == pytest.approx(-90, abs=0.3)
        assert friend.x == 0 and motion.done
        hero.say("jump", seconds=1)
        impulse = body.impulse(y=350)
        ticks(stage, 10)
        assert impulse.done and hero.y > -60 and not body.grounded
        assert hero._bubble is not None
        stage.remove(hero)
        with pytest.raises(PhysicsError):
            body.impulse(y=1)
        stage.add(hero)
        assert hero.body is not body and hero.body.velocity == (0, 0)
    finally:
        close(stage)
    assert body._native is None and hero._stage is None and floor._stage is None
    assert stage.physics._space is None


def test_forces_add_and_fractional_duration_integrates_once() -> None:
    stage = Stage(physics=True)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    actor = Sprite(PillowImage.new("RGBA", (10, 10)))
    stage.add(actor)
    stage._state = "running"
    stage.physics.gravity = (0, 0)
    try:
        actor.body.mass = 2
        force = actor.body.force(x=120, seconds=0.025)
        actor.body.force(x=120, seconds=0.025)
        ticks(stage, 3)
        assert force.done and actor.body.velocity[0] == pytest.approx(3)
        ticks(stage, 5)
        assert actor.body.velocity[0] == pytest.approx(3)
        actor.body.torque(100, seconds=0.05)
        ticks(stage, 4)
        assert actor.body.angular_velocity > 0
        actor.body.rotation_locked = True
        actor.body.torque(100, seconds=1)
        ticks(stage, 10)
        assert actor.body.angular_velocity == 0
    finally:
        close(stage)


def test_kinematic_glide_and_cancel_velocity() -> None:
    from plocks import Box

    stage = Stage(physics=True)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    platform = Sprite(PillowImage.new("RGBA", (20, 10)), body_type=BodyType.KINEMATIC)
    stage.add(platform)
    stage._state = "running"
    try:
        platform.body.shape = Box(20, 10)
        action = platform.glide_by(x=60, seconds=1)
        ticks(stage, 30)
        assert platform.x == pytest.approx(30)
        assert platform.body.velocity[0] == pytest.approx(60)
        action.cancel()
        assert platform.body.velocity == (0, 0)
        ticks(stage, 10)
        assert platform.x == pytest.approx(30)
        other = Sprite(platform.image)
        stage.add(other)
        other.glide_by(x=10, seconds=1)
        with pytest.raises(PhysicsError, match="kinematic"):
            _step(stage)
    finally:
        close(stage)


def test_shape_snapshot_scale_material_and_teleport_contacts() -> None:
    from plocks import Box, Circle

    stage = Stage(physics=True)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    hero = Sprite(PillowImage.new("RGBA", (20, 20)), y=50)
    floor = Sprite(PillowImage.new("RGBA", (100, 20)), body_type=BodyType.STATIC)
    stage.add(hero)
    stage.add(floor)
    stage._state = "running"
    try:
        hero.body.friction = 0.4
        hero.body.bounce = 0.2
        shape = hero.body.shape
        hero.image = PillowImage.new("RGBA", (60, 60))
        assert hero.body.shape is shape
        hero.scale = 2
        assert hero.body.shape is shape and hero.body.friction == 0.4
        hero.body.shape = Circle(10)
        assert hero.body.bounce == 0.2
        hero.body.bounce = 0
        ticks(stage, 120)
        assert hero.body.grounded and hero.body.touching(floor.body)
        velocity = hero.body.velocity
        hero.position = (0, 100)
        assert hero.body.velocity == velocity and not hero.body.grounded
        assert not hero.body.touching(floor.body)
        with pytest.raises(ValueError):
            hero.body.shape = Box(-1, 10)
        assert isinstance(hero.body.shape, Circle)
        with pytest.raises(PhysicsError):
            hero.body_type = BodyType.NONE
    finally:
        close(stage)


def test_terrain_edit_move_and_failed_edit_preserves_cells() -> None:
    stage = Stage(physics=True)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    tile = PillowImage.new("RGBA", (8, 8))
    world = TileMap(["#" * 4096 + "."], {"#": tile}, tile_size=(8, 8), solid={"#"})
    stage.add(world)
    try:
        with pytest.raises(PhysicsError, match="4096"):
            world.set_tile(row=0, column=4096, tile="#")
        assert world.get_tile(row=0, column=4096) is None
        world.set_tile(row=0, column=0, tile=None)
        world.set_tile(row=0, column=4096, tile="#")
        world.position = (10, 30)
        terrain = stage.physics._terrain[0]
        assert terrain.native is not None and tuple(terrain.native.position) == (10, 30)
        stage.remove(world)
        assert terrain.native is None and not stage.physics._terrain
    finally:
        close(stage)


def test_unbound_coroutine_force_detach_and_body_reset() -> None:
    from plocks import Action, Puppet
    from plocks._runtime import dispatch

    stage = Stage(physics=True)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    person = Puppet.stick_figure()
    stage.add(person)
    stage._state = "running"
    old = person.body

    @stage.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])
    def push(event: Event[Stage, GamepadPress]) -> Action:
        return person.body.force(x=10, seconds=10)

    stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.A))
    dispatch(stage)
    ticks(stage, 3)
    stage.remove(person)
    assert not stage._actions and old._native is None
    stage.add(person)
    assert person.body.mass == 1 and person.body.velocity == (0, 0)
    close(stage)


def test_optional_world_role_and_zero_duration() -> None:
    stage = Stage()
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    actor = Sprite(PillowImage.new("RGBA", (4, 4)))
    stage.add(actor)
    with pytest.raises(PhysicsError):
        _ = actor.body
    with pytest.raises(PhysicsError):
        _ = stage.physics
    close(stage)
    stage = Stage(physics=True)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    stage.add(actor)
    stage._state = "running"
    stage.physics.gravity = (0, 0)
    action = actor.body.force(x=100, seconds=0)
    ticks(stage, 2)
    assert action.done and actor.body.velocity == (0, 0)
    close(stage)


def test_shape_definitions_snapshot_points_and_body_requires_membership() -> None:
    from typing import cast

    from plocks import Body, Box, Circle, Point

    center = [2.0, 3.0]
    box = Box(10, 20, center=cast(Point, center))
    circle = Circle(5, center=cast(Point, center))
    center[0] = 100
    assert box.center == circle.center == (2, 3)
    with pytest.raises(TypeError, match="actor.body"):
        Body()


def test_offset_shape_keeps_anchor_and_center_impulse_has_no_torque() -> None:
    from plocks import Box, Image

    stage = Stage(physics=True)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    stage.physics.gravity = (0, 0)
    actor = Sprite(Image(PillowImage.new("RGBA", (20, 10)), anchor=(0, 0)), x=30, y=40)
    stage.add(actor)
    stage._state = "running"
    try:
        assert actor.position == (30, 40)
        actor.body.shape = Box(20, 10, center=(10, -5))
        actor.scale = 2
        assert actor.position == (30, 40)
        actor.body.impulse(y=10)
        ticks(stage, 2)
        assert actor.body.angular_velocity == pytest.approx(0)
        assert actor.body.velocity == pytest.approx((0, 10))
        actor.body.impulse(y=10, at=(actor.x + 40, actor.y))
        ticks(stage, 2)
        assert actor.body.angular_velocity < 0  # Upward force right of COM turns anticlockwise.
    finally:
        close(stage)


def test_kinematic_lift_supports_dynamic_body_and_stale_commands_cancel() -> None:
    stage = Stage(physics=True)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    lift = Sprite(PillowImage.new("RGBA", (100, 10)), body_type=BodyType.KINEMATIC)
    rider = Sprite(PillowImage.new("RGBA", (10, 10)), y=30)
    stage.add(lift)
    stage.add(rider)
    stage._state = "running"
    rider.body.rotation_locked = True
    try:
        ticks(stage, 90)
        assert rider.body.grounded
        before = rider.y
        motion = lift.glide_by(y=30, seconds=1)
        ticks(stage, 61)
        assert motion.done and lift.y == pytest.approx(30)
        assert rider.y == pytest.approx(before + 30, abs=0.5)
        # The rider keeps upward momentum briefly when the lift stops.
        ticks(stage, 30)
        assert rider.body.grounded
        future = rider.body.impulse(y=200, after=rider.wait(1))
        stage.remove(rider)
        stage.add(rider)
        assert future.cancelled
        rider.position = (0, 100)
        stage.physics.gravity = (0, 0)
        ticks(stage, 90)
        assert rider.body.velocity == pytest.approx((0, 0))
        assert not rider.body.grounded
    finally:
        close(stage)


def test_force_cancel_pause_and_failed_add_are_atomic() -> None:
    from plocks._runtime import advance

    stage = Stage(physics=True)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    stage.physics.gravity = (0, 0)
    actor = Sprite(PillowImage.new("RGBA", (8, 8)))
    stage.add(actor)
    stage._state = "running"
    try:
        force = actor.body.force(x=60, seconds=1)
        stage._last_wall = 0
        advance(stage, 1 / 60)
        assert actor.body.velocity[0] == pytest.approx(1)
        stage.pause()
        velocity = actor.body.velocity
        advance(stage, 10)
        assert actor.body.velocity == velocity
        stage.resume()
        force.cancel()
        ticks(stage, 10)
        assert actor.body.velocity == velocity
        oversized = Sprite(actor.image, scale=1e200)
        with pytest.raises(ValueError):
            stage.add(oversized)
        assert oversized._stage is None and oversized not in stage.objects
        assert len(stage.physics._bodies) == 1
    finally:
        close(stage)
