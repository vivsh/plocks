"""Combat convenience methods keep existing motion channels and stage ownership."""

from collections.abc import Iterator

import pytest

from plocks import BodyType, Image, PhysicsError, Puppet, Sprite, Stage, StageError, TileMap
from plocks._runtime import advance, close
from plocks._scripts import _step


def tick(stage: Stage, count: int = 1) -> None:
    for _ in range(count):
        advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)


@pytest.fixture
def arena() -> Iterator[Stage]:
    stage = Stage(physics=True)
    stage._state = "running"
    stage._last_wall = 0
    yield stage
    close(stage)


def test_walk_preserves_vertical_motion_and_y_writer(arena: Stage) -> None:
    actor = Sprite(Image.rectangle(10, 10), body_type=BodyType.KINEMATIC)
    arena.add(actor)
    vertical = actor.glide_by(y=100, seconds=1)
    _step(arena)
    actor.body.walk(speed=-120)
    assert not vertical.cancelled
    tick(arena)
    assert actor.body.velocity == pytest.approx((-120, 100))
    actor.body.walk(speed=0)
    assert actor.body.velocity == pytest.approx((0, 100))
    sideways = actor.glide_by(x=100, seconds=1)
    _step(arena)
    actor.body.walk(speed=50)
    assert sideways.cancelled and not vertical.cancelled
    previous = actor.body.velocity
    with pytest.raises(ValueError):
        actor.body.walk(speed=float("nan"))
    assert actor.body.velocity == previous


@pytest.mark.parametrize("mass", [1, 3])
def test_jump_is_grounded_mass_independent_and_preserves_sideways(arena: Stage, mass: int) -> None:
    hero = Sprite(Image.rectangle(20, 20), y=30)
    floor = TileMap(["##########"], {"#": hero.image}, tile_size=(32, 32), solid={"#"}, x=-160)
    arena.add(floor)
    arena.add(hero)
    hero.body.rotation_locked = True
    hero.body.mass = mass
    assert not hero.body.jump(height=80)
    tick(arena, 60)
    assert hero.body.grounded
    ground = hero.y
    hero.body.walk(speed=20)
    assert hero.body.jump(height=80)
    assert hero.body.velocity == pytest.approx((20, (2 * 900 * 80) ** 0.5))
    tick(arena)
    assert not hero.body.jump(height=80)
    apex = hero.y
    for _ in range(60):
        tick(arena)
        apex = max(apex, hero.y)
    assert apex - ground == pytest.approx(80, abs=2)
    arena.physics.gravity = (0, 0)
    with pytest.raises(PhysicsError):
        hero.body.jump(height=80)
    with pytest.raises(ValueError):
        hero.body.jump(height=0)


def test_sight_range_occlusion_ignore_and_nonphysical_target(arena: Stage) -> None:
    enemy = Sprite(Image.rectangle(10, 10), body_type=BodyType.STATIC)
    hero = Puppet.stick_figure()
    hero.position = (100, 0)
    hero.body_type = BodyType.NONE
    wall = Sprite(Image.rectangle(2, 80), x=50, body_type=BodyType.STATIC)
    for actor in (enemy, hero, wall):
        arena.add(actor)
    assert not enemy.can_see(hero)
    assert enemy.can_see(hero, ignore=(wall,))
    assert not enemy.can_see(hero, distance=99, ignore=(wall,))
    wall.body.sensor = True
    hero.visible = False
    assert enemy.can_see(hero, distance=100)
    assert hero.can_see(enemy)
    assert enemy.can_see(enemy, distance=0)
    with pytest.raises(ValueError):
        enemy.can_see(hero, distance=-1)
    hero.remove()
    with pytest.raises(StageError):
        enemy.can_see(hero)


def test_walk_jump_reject_stale_and_static(arena: Stage) -> None:
    actor = Sprite(Image.rectangle(10, 10), body_type=BodyType.STATIC)
    arena.add(actor)
    with pytest.raises(PhysicsError):
        actor.body.walk(speed=10)
    with pytest.raises(PhysicsError):
        actor.body.jump(height=10)
    body = actor.body
    actor.remove()
    with pytest.raises(PhysicsError):
        body.walk(speed=10)


def test_named_filters_affect_solver_support_and_body_queries(arena: Stage) -> None:
    hero = Sprite(Image.rectangle(10, 10), y=30)
    floor = Sprite(Image.rectangle(100, 10), body_type=BodyType.STATIC)
    arena.add(hero)
    arena.add(floor)
    hero.body.collision_group = "player"
    floor.body.collision_group = "floor"
    hero.body.collides_with = {"floor"}
    floor.body.collides_with = {"player"}
    tick(arena, 60)
    assert hero.body.grounded
    assert not hero.body.can_travel(distance=100, direction=180)
    hero.body.collides_with = set()
    assert not hero.body.grounded
    assert hero.body.can_travel(distance=100, direction=180)
    assert arena.physics.raycast(hero.position, (0, -100), ignore=(hero,)) is not None
    tick(arena, 30)
    assert hero.y < -20


def test_filter_validation_and_clone_shape_preservation(arena: Stage) -> None:
    hero = Sprite(Image.rectangle(10, 10))
    arena.add(hero)
    groups = {"enemy", "terrain"}
    hero.body.collision_group = "player"
    hero.body.collides_with = groups
    groups.clear()
    clone = hero.clone()
    assert clone.body.collides_with == frozenset({"enemy", "terrain"})
    assert clone.body.collision_group == "player"
    clone.image = Image.rectangle(20, 20)
    assert clone.body.collides_with == hero.body.collides_with
    with pytest.raises(ValueError):
        hero.body.collision_group = ""
    assert hero.body.collision_group == "player"


def test_fast_cloned_projectile_hits_thin_tile_then_reclones(arena: Stage) -> None:
    from plocks import CastHit, Event

    template = Sprite(Image.rectangle(10, 10), y=1000, body_type=BodyType.KINEMATIC)
    wall = TileMap(["#"], {"#": template.image}, tile_size=(2, 100), solid={"#"}, x=50, y=50)
    arena.add(template)
    arena.add(wall)
    template.body.projectile = True
    assert template.body.sensor
    results: list[CastHit] = []

    @template.on_hit
    def hit(event: Event[Sprite, CastHit]) -> None:
        assert event.target.x == pytest.approx(45)
        results.append(event.data)
        event.target.remove()

    for _ in range(5):
        bullet = template.clone()
        bullet.position = (0, 0)
        bullet.body.travel_along(speed=6000)
        tick(arena)
        assert bullet._stage is None
        assert template._stage is arena
    assert len(results) == 5
    assert all(result.target is wall and result.cell == (0, 0) for result in results)
    assert all(result.point == pytest.approx((50, 0)) for result in results)
    assert len(arena._hit_handlers) == 1


def test_projectile_filters_stop_once_and_relaunch(arena: Stage) -> None:
    from plocks import CastHit, Event

    bullet = Sprite(Image.rectangle(4, 4), body_type=BodyType.KINEMATIC)
    friend = Sprite(Image.rectangle(2, 20), x=20, body_type=BodyType.STATIC)
    enemy = Sprite(Image.rectangle(2, 20), x=50, body_type=BodyType.STATIC)
    for actor in (bullet, friend, enemy):
        arena.add(actor)
    friend.body.collision_group = "friend"
    enemy.body.collision_group = "enemy"
    bullet.body.collides_with = {"enemy"}
    bullet.body.projectile = True
    targets: list[object] = []

    @bullet.on_hit
    def hit(event: Event[Sprite, CastHit]) -> None:
        targets.append(event.data.target)

    bullet.body.travel_along(speed=6000)
    tick(arena, 10)
    assert targets == [enemy]
    assert bullet.x == pytest.approx(47)
    bullet.position = (0, 0)
    bullet.body.travel_along(speed=6000)
    tick(arena)
    assert targets == [enemy, enemy]
    with pytest.raises(PhysicsError):
        bullet.body.sensor = False
    with pytest.raises(PhysicsError):
        bullet.body.angular_velocity = 1
    bullet.body.projectile = False
    bullet.body.sensor = False


def test_projectile_relative_translation_crosses_between_samples(arena: Stage) -> None:
    from plocks import CastHit, Event

    bullet = Sprite(Image.rectangle(2, 2), body_type=BodyType.KINEMATIC)
    target = Sprite(Image.rectangle(2, 2), x=10, y=10, body_type=BodyType.KINEMATIC)
    arena.add(bullet)
    arena.add(target)
    bullet.body.projectile = True
    targets: list[object] = []

    @bullet.on_hit
    def hit(event: Event[Sprite, CastHit]) -> None:
        targets.append(event.data.target)

    bullet.body.velocity = (4800, 0)
    target.body.velocity = (0, -4800)
    tick(arena)
    assert targets == [target]


def test_projectile_mode_and_connections_validate_before_mutation(arena: Stage) -> None:
    bullet = Sprite(Image.rectangle(10, 10), body_type=BodyType.KINEMATIC)
    heavy = Sprite(Image.rectangle(10, 10), x=50)
    arena.add(bullet)
    arena.add(heavy)
    with pytest.raises(PhysicsError):
        heavy.body.projectile = True
    assert not heavy.body.projectile and not heavy.body.sensor
    link = arena.physics.rope(bullet, heavy, length=50)
    with pytest.raises(PhysicsError):
        bullet.body.projectile = True
    assert not bullet.body.projectile and not bullet.body.sensor
    link.disconnect()
    bullet.body.projectile = True
    with pytest.raises(PhysicsError):
        arena.physics.rope(bullet, heavy, length=50)
    assert not arena.physics._connections


def test_projectile_respects_one_way_top(arena: Stage) -> None:
    from plocks import CastHit, Event

    platform = Sprite(Image.rectangle(100, 10), body_type=BodyType.STATIC, one_way=True)
    bullet = Sprite(Image.rectangle(4, 4), y=-30, body_type=BodyType.KINEMATIC)
    arena.add(platform)
    arena.add(bullet)
    bullet.body.projectile = True
    hits: list[CastHit] = []

    @bullet.on_hit
    def hit(event: Event[Sprite, CastHit]) -> None:
        hits.append(event.data)

    bullet.body.velocity = (0, 6000)
    tick(arena)
    assert hits == [] and bullet.y > platform.y
    bullet.body.velocity = (0, -6000)
    tick(arena)
    assert len(hits) == 1 and hits[0].target is platform
    assert bullet.bounds.bottom == pytest.approx(platform.bounds.top)


def test_puppet_projectile_inherits_typed_hit_and_origin(arena: Stage) -> None:
    from plocks import CastHit, Event, Joint, Skeleton

    skeleton = Skeleton({"root": Joint(parent=None)})
    bullet = Puppet(skeleton, parts={"root": Image.rectangle(4, 4)}, body_type=BodyType.KINEMATIC)
    bullet.position = (0, 1000)
    enemy = Sprite(Image.rectangle(2, 30), x=40, body_type=BodyType.STATIC)
    arena.add(bullet)
    arena.add(enemy)
    bullet.body.projectile = True
    results: list[Puppet] = []

    @bullet.on_hit
    def hit(event: Event[Puppet, CastHit]) -> None:
        assert event.data.target is enemy
        results.append(event.target)
        event.target.remove()

    clone = bullet.clone()
    clone.position = (0, 0)
    clone.body.travel_along(speed=6000)
    tick(arena)
    assert results == [clone]
    assert bullet.clone_count == arena.clone_count == 0
    assert bullet._stage is arena
