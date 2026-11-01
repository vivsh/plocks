"""Persistent containment shares the ordinary movement and physics lifetimes."""

from unittest.mock import patch

import pygame
import pytest

from plocks import (
    Actor,
    BodyType,
    Bounds,
    Box,
    Circle,
    Event,
    GamepadButton,
    Image,
    Joint,
    Key,
    PhysicsError,
    Puppet,
    RotationStyle,
    Skeleton,
    Sprite,
    Stage,
)
from plocks._containment import _footprint
from plocks._runtime import _key, advance, close


def tick(stage: Stage, count: int = 1) -> None:
    for _ in range(count):
        advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)


def test_first_held_walk_jump_and_independent_glide() -> None:
    stage = Stage(physics=True)
    hero = Sprite(Image.rectangle(20, 20))
    friend = Sprite(hero.image, y=50, body_type=BodyType.NONE)
    stage.add(hero)
    stage.add(friend)
    hero.keep_inside(Bounds(-100, -100, 100, 100))
    hero.body.rotation_locked = True
    stage._state, stage._last_wall = "running", 0.0
    try:
        friend.keep_inside(Bounds(-100, -100, 100, 100))
        glide = friend.glide_by(x=300, seconds=1)
        # A held control issues the same walk command every update.
        for _ in range(120):
            hero.body.walk(speed=150)
            tick(stage)
        assert hero.position == pytest.approx((90, -90), abs=0.15)
        assert hero.body.grounded
        assert friend.x == 90 and glide.done
        assert hero.body.jump(height=40)
        tick(stage, 10)
        assert hero.y > -70 and not hero.body.grounded
        tick(stage, 100)
        assert hero.body.grounded
        old = hero.body._boundary_native
        hero.keep_inside(None)
        assert old is not None and old.space is None and not old.shapes
        tick(stage, 20)
        assert hero.y < -100
    finally:
        close(stage)
    assert hero._stage is None and hero._movement_bounds is None


def test_private_walls_only_block_their_owner() -> None:
    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    hero = Sprite(Image.rectangle(10, 10))
    friend = Sprite(hero.image, x=-70)
    stage.add(hero)
    stage.add(friend)
    hero.keep_inside(Bounds(-50, -50, 50, 50))
    hero.body.collides_with = frozenset()
    friend.body.collides_with = frozenset()
    stage._state, stage._last_wall = "running", 0.0
    try:
        hero.body.velocity = (200, 0)
        friend.body.velocity = (200, 0)
        tick(stage, 60)
        assert hero.x == pytest.approx(45)
        assert friend.x == pytest.approx(130)
    finally:
        close(stage)


def make_actor(puppet: bool = False, *, role: BodyType = BodyType.DYNAMIC) -> Actor:
    image = Image.rectangle(20, 10, color="orange")
    return (
        Puppet(Skeleton({"root": Joint(None)}), parts={"root": image}, body_type=role)
        if puppet
        else Sprite(image, body_type=role)
    )


def inside(actor: Actor, area: Bounds) -> None:
    box = _footprint(actor)
    assert box.left >= area.left - 1e-7 and box.right <= area.right + 1e-7
    assert box.bottom >= area.bottom - 1e-7 and box.top <= area.top + 1e-7


@pytest.mark.parametrize("puppet", [False, True])
@pytest.mark.parametrize("physical", [False, True])
def test_immediate_writes_held_keys_and_disable(puppet: bool, physical: bool) -> None:
    stage = Stage(physics=physical)
    actor = make_actor(puppet)
    area = Bounds(-50, -40, 50, 40)
    actor.keep_inside(area)
    stage.add(actor)
    if physical:
        stage.physics.gravity = (0, 0)
    stage._state, stage._last_wall = "running", 0.0
    try:
        stage.gamepads[0].map_key(Key.RIGHT, GamepadButton.RIGHT)

        @stage.on_update
        def held(event: Event[Stage, float]) -> None:
            if stage.gamepads[0].is_down(GamepadButton.RIGHT):
                actor.x += 200 * event.data

        _key(stage, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
        tick(stage, 90)
        assert actor.x == pytest.approx(40)
        actor.position = (-500, -500)
        assert actor.position == pytest.approx((-40, -35))
        actor.move_to(x=500, y=500)
        tick(stage)
        inside(actor, area)
        assert actor.position == pytest.approx((40, 35))
        actor.keep_inside(None)
        actor.position = (500, 500)
        assert actor.position == (500, 500)
    finally:
        close(stage)


@pytest.mark.parametrize("puppet", [False, True])
@pytest.mark.parametrize("role", list(BodyType))
def test_all_body_roles_stay_inside_without_changing_role(puppet: bool, role: BodyType) -> None:
    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    actor = make_actor(puppet, role=role)
    area = Bounds(-60, -50, 60, 50)
    stage.add(actor)
    actor.keep_inside(area)
    stage._state, stage._last_wall = "running", 0.0
    try:
        if role not in (BodyType.NONE, BodyType.STATIC):
            actor.body.velocity = (1000, -1000)
            tick(stage, 20)
        else:
            actor.position = (1000, -1000)
        inside(actor, area)
        assert actor.body_type is role
    finally:
        close(stage)


@pytest.mark.parametrize("puppet", [False, True])
@pytest.mark.parametrize("physical", [False, True])
def test_glide_completion_after_chain_pause_and_no_cancellation(
    puppet: bool, physical: bool
) -> None:
    stage = Stage(physics=physical)
    actor = make_actor(puppet, role=BodyType.KINEMATIC)
    stage.add(actor)
    area = Bounds(-60, -50, 60, 50)
    actor.keep_inside(area)
    stage._state, stage._last_wall = "running", 0.0
    try:
        first = actor.glide_by(x=1000, seconds=0.2)
        second = actor.glide_to(x=0, seconds=0.2, after=first)
        tick(stage, 6)
        assert not first.done and not first.cancelled
        before = actor.position
        stage.pause()
        tick(stage, 20)
        assert actor.position == before and not first.done
        stage.resume()
        tick(stage, 25)
        assert first.done and second.done and not first.cancelled
        assert actor.x == pytest.approx(0)
        zero = actor.glide_by(y=1000, seconds=0)
        tick(stage, 2)
        assert zero.done and actor.y == pytest.approx(45)
    finally:
        close(stage)


@pytest.mark.parametrize("puppet", [False, True])
def test_sensor_containment_does_not_fake_grounded(puppet: bool) -> None:
    stage = Stage(physics=True)
    actor = make_actor(puppet)
    stage.add(actor)
    actor.body.sensor = True
    actor.keep_inside(Bounds(-60, -50, 60, 50))
    stage._state, stage._last_wall = "running", 0.0
    try:
        tick(stage, 90)
        assert actor.y == -45 and actor.body.velocity[1] == 0
        assert not actor.body.grounded and not actor.body.jump(height=20)
    finally:
        close(stage)


@pytest.mark.parametrize("direction", [0, 45, 90, 135, 270])
@pytest.mark.parametrize("puppet", [False, True])
def test_visual_corners_anchor_rotation_scale_and_style(puppet: bool, direction: float) -> None:
    actor = make_actor(puppet)
    area = Bounds(-100, -80, 100, 80)
    actor.position = (1000, -1000)
    actor.direction, actor.scale = direction, 2
    actor.keep_inside(area)
    inside(actor, area)
    for style in RotationStyle:
        actor.rotation_style = style
        actor.position = (-1000, 1000)
        inside(actor, area)
        assert actor.bounds == _footprint(actor)
    before = actor.position, actor.scale, actor.direction, actor.rotation_style
    with pytest.raises(ValueError, match="too large"):
        actor.scale = 100
    assert (actor.position, actor.scale, actor.direction, actor.rotation_style) == before


@pytest.mark.parametrize("shape", [Box(12, 8, (5, -2)), Circle(8, (4, 2))])
def test_custom_collider_and_shape_fit_respect_boundary(shape: Box | Circle) -> None:
    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    actor = Sprite(Image.rectangle(100, 100))
    stage.add(actor)
    actor.body.shape = shape
    area = Bounds(-30, -30, 30, 30)
    actor.keep_inside(area)
    try:
        actor.position = (100, 100)
        inside(actor, area)
        assert actor.bounds.right > area.right  # Artwork may overhang a custom collider.
        assert actor.body.can_fit_shape(shape)
        assert not actor.body.can_fit_image(Image.rectangle(100, 100))
        before = actor.body.shape, actor.position
        with pytest.raises(ValueError, match="too large"):
            actor.body.shape = Box(100, 100)
        assert (actor.body.shape, actor.position) == before
        with pytest.raises(ValueError):
            actor.body.use_actor_shape()
        assert not actor.body.auto_shape
        actor.direction = 45
        inside(actor, area)
    finally:
        close(stage)


@pytest.mark.parametrize("physical", [False, True])
def test_image_changes_fit_reject_before_cancel_and_timed_sampling(physical: bool) -> None:
    stage = Stage(physics=physical)
    actor = make_actor(role=BodyType.KINEMATIC)
    assert isinstance(actor, Sprite)
    stage.add(actor)
    area = Bounds(-40, -30, 40, 30)
    actor.keep_inside(area)
    actor.position = (100, 100)
    stage._state, stage._last_wall = "running", 0.0
    try:
        action = actor.images((actor.image, Image.rectangle(40, 20)), fps=10)
        tick(stage)
        old = actor.image, actor.position
        with pytest.raises(ValueError):
            actor.image = Image.rectangle(100, 100)
        assert not action.cancelled and (actor.image, actor.position) == old
        tick(stage, 15)
        assert action.done and actor.image.width == 40
        inside(actor, area)
        actor.images((actor.image, Image.rectangle(100, 100)), fps=60)
        with pytest.raises(ValueError, match="too large"):
            tick(stage, 3)
    finally:
        close(stage)
    assert actor._stage is None


@pytest.mark.parametrize("physical", [False, True])
def test_puppet_pose_part_changes_and_bounds(physical: bool) -> None:
    stage = Stage(physics=physical)
    actor = Puppet(
        Skeleton({"root": Joint(None), "hand": Joint("root", offset=(30, 0))}),
        parts={"root": Image.rectangle(10, 10), "hand": Image.rectangle(10, 20)},
    )
    stage.add(actor)
    area = Bounds(-60, -50, 60, 50)
    actor.keep_inside(area)
    actor.position = (100, 100)
    stage._state, stage._last_wall = "running", 0.0
    if physical:
        stage.physics.gravity = (0, 0)
        actor.body.rotation_locked = True
    try:
        rest = actor.pose
        turned = rest.with_angles({"root": 270})
        if physical:
            assert not actor.body.can_fit_pose(turned)
        actor.pose = turned
        inside(actor, area)
        action = actor.poses((turned, rest, turned), fps=10)
        tick(stage, 15)
        assert action.done
        inside(actor, area)
        action = actor.set_part_image("hand", Image.rectangle(15, 20))
        tick(stage)
        assert action.done
        inside(actor, area)
        actor.set_part_image("hand", Image.rectangle(300, 300))
        with pytest.raises(ValueError, match="too large"):
            tick(stage)
        assert actor.parts["hand"].width == 15
    finally:
        close(stage)


def test_clone_rule_native_independence_removal_readd_and_close() -> None:
    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    actor = Sprite(Image.rectangle(100, 100))
    stage.add(actor)
    actor.body.shape = Box(10, 10)
    area = Bounds(-30, -30, 30, 30)
    actor.keep_inside(area)
    clone = actor.clone()
    assert clone._movement_bounds is area and clone.body.shape == actor.body.shape
    assert clone.body._boundary_native is not actor.body._boundary_native
    clone.position = (100, 100)
    inside(clone, area)
    old_body = clone.body
    old_wall = old_body._boundary_native
    clone.remove()
    assert old_body._boundary_native is None and old_wall is not None and old_wall.space is None
    assert clone._movement_bounds is area and actor._stage is stage
    # Re-add uses the ordinary automatic shape, which no longer fits.
    with pytest.raises(ValueError):
        stage.add(clone)
    assert clone._stage is None and clone not in stage.objects
    clone.keep_inside(None)
    stage.add(clone)
    clone.body.shape = Box(10, 10)
    clone.keep_inside(area)
    active = clone.body
    close(stage)
    close(stage)
    assert active._boundary_native is None and active._native is None
    assert actor._movement_bounds is area and not stage.physics._bodies


@pytest.mark.parametrize("puppet", [False, True])
def test_nonphysical_clone_and_readd(puppet: bool) -> None:
    stage = Stage()
    actor = make_actor(puppet)
    area = Bounds(-50, -50, 50, 50)
    actor.keep_inside(area)
    stage.add(actor)
    clone = actor.clone()
    assert clone._movement_bounds is area
    clone.remove()
    stage.add(clone)
    clone.position = (100, 100)
    inside(clone, area)
    close(stage)


def test_failed_reconfiguration_and_attachment_preserve_resources() -> None:
    stage = Stage(physics=True)
    actor = make_actor()
    stage.add(actor)
    area = Bounds(-50, -50, 50, 50)
    actor.keep_inside(area)
    wall, before = actor.body._boundary_native, actor.position
    try:
        with patch("plocks._containment._walls", side_effect=PhysicsError("native failure")):
            with pytest.raises(PhysicsError, match="native failure"):
                actor.keep_inside(Bounds(-40, -40, 40, 40))
            other = make_actor()
            other.keep_inside(area)
            with pytest.raises(PhysicsError, match="native failure"):
                stage.add(other)
        assert actor._movement_bounds is area and actor.body._boundary_native is wall
        assert actor.position == before
        assert other._stage is None and len(stage.physics._bodies) == 1
        assert wall is not None and stage.physics._space is not None
        assert len(stage.physics._space.shapes) == 5
    finally:
        close(stage)


@pytest.mark.parametrize(
    "bad", [Bounds(0, 0, 0, 10), Bounds(0, 0, 10, 0), Bounds(-1e308, 0, 1e308, 10)]
)
def test_invalid_bounds_do_not_change_policy_or_position(bad: Bounds) -> None:
    actor = make_actor()
    area = Bounds(-50, -50, 50, 50)
    actor.keep_inside(area)
    with pytest.raises(ValueError):
        actor.keep_inside(bad)
    assert actor._movement_bounds is area and actor.position == (0, 0)


def test_enabling_does_not_teleport_into_terrain_or_move_connections() -> None:
    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    actor = Sprite(Image.rectangle(10, 10), x=80)
    blocker = Sprite(Image.rectangle(10, 10), x=45, body_type=BodyType.STATIC)
    stage.add(actor)
    stage.add(blocker)
    try:
        with pytest.raises(PhysicsError, match="solid geometry"):
            actor.keep_inside(Bounds(-50, -50, 50, 50))
        assert actor.x == 80 and actor._movement_bounds is None
        link = stage.physics.rope((0, 0), actor, length=100)
        with pytest.raises(PhysicsError, match="connected actor"):
            actor.keep_inside(Bounds(-50, -50, 50, 50))
        assert link.connected and actor.body._boundary_native is None
    finally:
        close(stage)


def test_feasible_rope_hinge_and_motor_remain_connected() -> None:
    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    actor = Sprite(Image.rectangle(10, 20), x=20)
    stage.add(actor)
    actor.keep_inside(Bounds(-80, -80, 80, 80))
    rope = stage.physics.rope((0, 0), actor, length=50)
    stage._state, stage._last_wall = "running", 0.0
    try:
        actor.body.velocity = (100, 0)
        tick(stage, 120)
        assert rope.connected and actor.x < 51
        rope.disconnect()
        actor.position = (0, 0)
        hinge = stage.physics.hinge((0, 0), actor)
        motor = hinge.motor(speed=90, max_torque=1000)
        tick(stage, 120)
        assert hinge.connected and motor.connected
        assert actor._movement_bounds is not None
        inside(actor, actor._movement_bounds)
    finally:
        close(stage)


def test_one_way_platform_and_high_speed_do_not_escape() -> None:
    stage = Stage(physics=True)
    actor = Sprite(Image.rectangle(20, 10), body_type=BodyType.KINEMATIC, one_way=True)
    stage.add(actor)
    area = Bounds(-50, -50, 50, 50)
    actor.keep_inside(area)
    stage._state, stage._last_wall = "running", 0.0
    try:
        actor.body.velocity = (100000, -100000)
        tick(stage)
        inside(actor, area)
        assert actor.position == (40, -45)
        assert actor.body.velocity == (0, 0)
    finally:
        close(stage)


def test_boundary_is_fixed_world_space_and_not_a_hit_or_cast_target() -> None:
    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    actor = make_actor()
    stage.add(actor)
    area = stage.world_bounds
    actor.keep_inside(area)
    hits: list[object] = []
    actor.on_hit(lambda event: hits.append(event.data))
    stage.camera = (1000, 1000)
    stage._state, stage._last_wall = "running", 0.0
    try:
        actor.body.velocity = (3000, 0)
        tick(stage, 30)
        inside(actor, area)
        assert not hits
        assert stage.physics.raycast((actor.x, 50), (actor.x + 200, 50)) is None
        assert actor.body.can_travel(distance=100, direction=90)
    finally:
        close(stage)


@pytest.mark.parametrize("puppet", [False, True])
def test_velocity_preserves_tangent_and_inward_motion(puppet: bool) -> None:
    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    actor = make_actor(puppet)
    stage.add(actor)
    area = Bounds(-50, -50, 50, 50)
    actor.keep_inside(area)
    try:
        actor.body.velocity = (100, 25)
        actor.position = (100, 0)
        assert actor.body.velocity == (0, 25)
        actor.body.velocity = (-100, 25)
        actor.position = (100, 0)
        assert actor.body.velocity == (-100, 25)
        actor.visible = False
        actor.keep_inside(None)
        assert actor.body.velocity == (-100, 25)
        actor.position = (200, 0)
        assert actor.position == (200, 0)
    finally:
        close(stage)


def test_stale_body_queries_raise_even_for_an_impossible_shape() -> None:
    stage = Stage(physics=True)
    actor = make_actor()
    stage.add(actor)
    actor.keep_inside(Bounds(-50, -50, 50, 50))
    body = actor.body
    actor.remove()
    try:
        with pytest.raises(PhysicsError):
            body.can_fit_shape(Box(1000, 1000))
        with pytest.raises(PhysicsError):
            body.shape = Box(1000, 1000)
    finally:
        close(stage)


def test_resource_budget_replacement_and_rollback() -> None:
    stage = Stage(physics=True)
    area = Bounds(-50, -50, 50, 50)
    try:
        for _ in range(1024):
            actor = make_actor()
            stage.add(actor)
            actor.keep_inside(area)
        # Reconfiguring an existing owner consumes the same budget slot.
        old = actor.body._boundary_native
        actor.keep_inside(Bounds(-60, -60, 60, 60))
        assert old is not None and old.space is None
        extra = make_actor()
        extra.keep_inside(area)
        with pytest.raises(PhysicsError, match="1024 bounded"):
            stage.add(extra)
        assert extra._stage is None and len(stage.physics._bodies) == 1024
        space = stage.physics._space
        assert space is not None and len(space.shapes) == 5120
    finally:
        close(stage)


def test_incompatible_runtime_connection_fails_instead_of_teleporting() -> None:
    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    actor = make_actor()
    stage.add(actor)
    actor.keep_inside(Bounds(-20, -20, 20, 20))
    stage.physics.rope((200, 0), actor, length=10)
    stage._state, stage._last_wall = "running", 0.0
    try:
        with pytest.raises(PhysicsError, match="connected actor"):
            tick(stage, 120)
    finally:
        close(stage)
    assert actor._stage is None and not stage.physics._connections


def test_rendering_uses_contained_geometry_and_camera_translation() -> None:
    from plocks._render import frame

    stage = Stage(width=100, height=80, background="black")
    actor = Sprite(Image.rectangle(20, 10, color="orange"))
    stage.add(actor)
    actor.keep_inside(Bounds(-40, -30, 40, 30))
    actor.position = (200, 200)
    pygame.display.init()
    stage._target = pygame.display.set_mode((100, 80))
    stage.camera = (10, 5)
    try:
        frame(stage)
        # World box (20, 20)-(40, 30), shifted by camera, is screen (60, 15)-(80, 25).
        assert tuple(stage._target.get_at((65, 20)))[:3] == (255, 165, 0)
        assert tuple(stage._target.get_at((81, 20)))[:3] == (0, 0, 0)
        assert actor.position == (30, 25)
    finally:
        close(stage)


@pytest.mark.parametrize("physical", [False, True])
def test_large_finite_positions_clip_to_the_edge_without_losing_image_extent(
    physical: bool,
) -> None:
    stage = Stage(physics=physical)
    actor = make_actor()
    stage.add(actor)
    actor.keep_inside(Bounds(-50, -50, 50, 50))
    try:
        actor.position = (1e100, -1e100)
        assert actor.position == (40, -45)
        inside(actor, Bounds(-50, -50, 50, 50))
    finally:
        close(stage)
