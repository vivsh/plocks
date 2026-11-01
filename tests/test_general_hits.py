"""One typed physical-hit system for body contact and fast swept projectiles."""

from collections.abc import Iterator

import pytest

from plocks import BodyType, Collision, Event, Image, Sprite, Stage, TileMap
from plocks._runtime import advance, close


def tick(stage: Stage, count: int = 1) -> None:
    for _ in range(count):
        advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)


@pytest.fixture
def arena() -> Iterator[Stage]:
    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    stage._state = "running"
    stage._last_wall = 0
    yield stage
    close(stage)


def test_hero_contact_once_then_separate_and_rehit(arena: Stage) -> None:
    hero = Sprite(Image.rectangle(10, 10))
    wall = Sprite(Image.rectangle(10, 100), x=30, body_type=BodyType.STATIC)
    arena.add(hero)
    arena.add(wall)
    hero.body.rotation_locked = True
    hits: list[Collision] = []

    @hero.on_hit
    def bumped(event: Event[Sprite, Collision]) -> None:
        assert event.source is arena and event.target is hero
        hits.append(event.data)

    hero.body.walk(speed=120)
    tick(arena, 60)
    assert len(hits) == 1 and hits[0].target is wall
    assert hits[0].normal == pytest.approx((-1, 0))
    hero.position = (0, 0)
    hero.body.walk(speed=0)
    tick(arena, 2)
    hero.body.walk(speed=120)
    tick(arena, 30)
    assert len(hits) == 2


def test_swept_clone_same_event_and_reverse_recipient(arena: Stage) -> None:
    original = Sprite(Image.rectangle(4, 4), y=1000, body_type=BodyType.KINEMATIC)
    wall = Sprite(Image.rectangle(2, 30), x=50, body_type=BodyType.STATIC)
    arena.add(original)
    arena.add(wall)
    original.body.projectile = True
    impacts: list[Collision] = []
    reverse: list[Collision] = []

    @original.on_hit
    def impact(event: Event[Sprite, Collision]) -> None:
        impacts.append(event.data)

    @wall.on_hit
    def contacted(event: Event[Sprite, Collision]) -> None:
        reverse.append(event.data)

    copy = original.clone()
    copy.position = (0, 0)
    copy.body.travel_along(speed=6000)
    tick(arena, 10)
    assert len(impacts) == len(reverse) == 1
    assert impacts[0].target is wall and reverse[0].target is copy
    assert impacts[0].normal == pytest.approx((-1, 0))
    assert reverse[0].normal == pytest.approx((1, 0))
    copy.remove()
    assert not arena._hit_contacts
    assert original._stage is arena


def test_resting_floor_and_tile_seam_is_one_owner_contact(arena: Stage) -> None:
    arena.physics.gravity = (0, -900)
    hero = Sprite(Image.rectangle(16, 16), y=30)
    world = TileMap(["##########"], {"#": hero.image}, tile_size=(32, 32), solid={"#"}, x=-160)
    arena.add(hero)
    arena.add(world)
    hero.body.rotation_locked = True
    hero.body.friction = 0
    hits: list[Collision] = []

    @hero.on_hit
    def landed(event: Event[Sprite, Collision]) -> None:
        hits.append(event.data)

    tick(arena, 60)
    assert len(hits) == 1 and hits[0].target is world and hits[0].cell is not None
    hero.body.walk(speed=60)
    tick(arena, 90)
    assert len(hits) == 1


@pytest.mark.parametrize("first_role", [BodyType.DYNAMIC, BodyType.KINEMATIC, BodyType.STATIC])
@pytest.mark.parametrize("second_role", [BodyType.DYNAMIC, BodyType.KINEMATIC, BodyType.STATIC])
def test_all_physical_roles_edge_contact_both_receivers(
    arena: Stage, first_role: BodyType, second_role: BodyType
) -> None:
    first = Sprite(Image.rectangle(10, 10), body_type=first_role)
    second = Sprite(first.image, x=10, body_type=second_role)
    arena.add(first)
    arena.add(second)
    a: list[Collision] = []
    b: list[Collision] = []

    @first.on_hit
    def left(event: Event[Sprite, Collision]) -> None:
        a.append(event.data)

    @second.on_hit
    def right(event: Event[Sprite, Collision]) -> None:
        b.append(event.data)

    tick(arena, 20)
    assert len(a) == len(b) == 1
    assert a[0].target is second and b[0].target is first
    assert a[0].normal == pytest.approx((-1, 0))
    assert b[0].normal == pytest.approx((1, 0))


def test_visual_touch_stays_independent_from_physical_geometry_and_filters(arena: Stage) -> None:
    from plocks import Box

    hero = Sprite(Image.rectangle(40, 40))
    enemy = Sprite(hero.image, x=25, body_type=BodyType.STATIC)
    arena.add(hero)
    arena.add(enemy)
    hero.body.shape = Box(10, 10)
    enemy.body.shape = Box(10, 10)
    hero.body.rotation_locked = True
    touches: list[Sprite] = []
    hits: list[Collision] = []

    @hero.on_touch(enemy)
    def overlap(event: Event[Sprite, Sprite]) -> None:
        touches.append(event.data)

    @hero.on_hit
    def collision(event: Event[Sprite, Collision]) -> None:
        hits.append(event.data)

    tick(arena)
    assert touches == [enemy] and hits == []
    hero.position = (15, 0)
    tick(arena)
    assert len(hits) == 1 and len(touches) == 1
    hero.body.collides_with = set()
    tick(arena)
    assert not arena._hit_contacts and hero.touching(enemy)
    hero.body.collides_with = None
    tick(arena)
    assert len(hits) == 2 and len(touches) == 1


def test_sensor_contacts_notify_without_blocking_and_reenter(arena: Stage) -> None:
    hero = Sprite(Image.rectangle(10, 10), body_type=BodyType.KINEMATIC)
    zone = Sprite(Image.rectangle(10, 10), x=20, body_type=BodyType.STATIC)
    arena.add(hero)
    arena.add(zone)
    zone.body.sensor = True
    hits: list[Collision] = []

    @hero.on_hit
    def entered(event: Event[Sprite, Collision]) -> None:
        hits.append(event.data)

    hero.body.walk(speed=120)
    tick(arena, 25)
    assert len(hits) == 1 and hero.x == pytest.approx(50)
    hero.body.walk(speed=-120)
    tick(arena, 25)
    assert len(hits) == 2


def test_fast_projectile_sensor_before_wall_not_behind_wall(arena: Stage) -> None:
    bullet = Sprite(Image.rectangle(4, 4), body_type=BodyType.KINEMATIC)
    before = Sprite(Image.rectangle(2, 30), x=30, body_type=BodyType.STATIC)
    wall = Sprite(before.image, x=70, body_type=BodyType.STATIC)
    behind = Sprite(before.image, x=100, body_type=BodyType.STATIC)
    for obj in (bullet, before, wall, behind):
        arena.add(obj)
    before.body.sensor = behind.body.sensor = True
    bullet.body.projectile = True
    hits: list[Collision] = []

    @bullet.on_hit
    def impact(event: Event[Sprite, Collision]) -> None:
        hits.append(event.data)

    bullet.body.travel_along(speed=12000)
    tick(arena, 10)
    assert [hit.target for hit in hits] == [before, wall]
    assert bullet.x == pytest.approx(67)
    ray = arena.physics.raycast((0, 0), (200, 0), ignore=(bullet,))
    assert ray is not None and ray.target is wall


@pytest.mark.parametrize("tile", [False, True])
def test_one_way_passes_underside_then_reports_landing(arena: Stage, tile: bool) -> None:
    image = Image.rectangle(100, 10)
    platform = (
        TileMap(["P"], {"P": image}, tile_size=(100, 10), one_way={"P"}, x=-50, y=5)
        if tile
        else Sprite(image, body_type=BodyType.STATIC, one_way=True)
    )
    hero = Sprite(Image.rectangle(10, 10), y=-40)
    arena.add(platform)
    arena.add(hero)
    hero.body.rotation_locked = True
    hits: list[Collision] = []

    @hero.on_hit
    def collision(event: Event[Sprite, Collision]) -> None:
        hits.append(event.data)

    hero.body.velocity = (0, 120)
    tick(arena, 50)
    assert hero.y > 50 and not hits
    hero.body.velocity = (0, -120)
    tick(arena, 50)
    assert len(hits) == 1 and hits[0].target is platform
    assert hits[0].normal == pytest.approx((0, 1))


def test_noncolliding_link_ignores_contacts_until_enabled(arena: Stage) -> None:
    a = Sprite(Image.rectangle(10, 10))
    b = Sprite(a.image, x=5)
    arena.add(a)
    arena.add(b)
    rope = arena.physics.rope(a, b, length=20, collide=False)
    hits: list[Collision] = []

    @a.on_hit
    def hit(event: Event[Sprite, Collision]) -> None:
        hits.append(event.data)

    tick(arena)
    assert not hits
    rope.collide = True
    tick(arena)
    assert len(hits) == 1 and hits[0].target is b


def test_removal_pause_and_handler_snapshot(arena: Stage) -> None:
    hero = Sprite(Image.rectangle(10, 10), body_type=BodyType.KINEMATIC)
    wall = Sprite(hero.image, x=10, body_type=BodyType.STATIC)
    arena.add(hero)
    arena.add(wall)
    events: list[str] = []

    @hero.on_hit
    def first(event: Event[Sprite, Collision]) -> None:
        events.append("first")
        wall.remove()

    @hero.on_hit
    def second(event: Event[Sprite, Collision]) -> None:
        events.append("second")

    arena.pause()
    tick(arena, 20)
    assert not events
    arena.resume()
    tick(arena, 2)
    assert events == ["first"] and not arena._hit_contacts
    arena.add(wall)
    tick(arena, 2)
    assert events == ["first", "first"] and not arena._hit_contacts


def test_clone_history_is_fresh_and_puppet_receiver(arena: Stage) -> None:
    from plocks import Joint, Puppet, Skeleton

    rig = Skeleton({"root": Joint(parent=None)})
    original = Puppet(rig, parts={"root": Image.rectangle(10, 10)}, body_type=BodyType.KINEMATIC)
    original.position = (0, 1000)
    wall = Sprite(Image.rectangle(10, 10), x=10, body_type=BodyType.STATIC)
    arena.add(original)
    arena.add(wall)
    wall.body.collision_group = "wall"
    original.body.collides_with = {"wall"}
    receivers: list[Puppet] = []

    @original.on_hit
    def hit(event: Event[Puppet, Collision]) -> None:
        receivers.append(event.target)

    first, second = original.clone(), original.clone()
    first.position = second.position = (0, 0)
    tick(arena, 10)
    assert receivers == [first, second]
    assert len(arena._hit_contacts) == 2
    first.remove()
    assert len(arena._hit_contacts) == 1
    close(arena)
    assert not arena._hit_contacts


@pytest.mark.parametrize("role", [BodyType.DYNAMIC, BodyType.KINEMATIC])
def test_history_and_batch_limits_and_callback_errors(
    arena: Stage, monkeypatch: pytest.MonkeyPatch, role: BodyType
) -> None:
    from plocks import StageError, _collisions

    hero = Sprite(Image.rectangle(30, 30), body_type=role)
    a = Sprite(Image.rectangle(10, 10), x=-10, body_type=BodyType.STATIC)
    b = Sprite(a.image, x=10, body_type=BodyType.STATIC)
    for obj in (hero, a, b):
        arena.add(obj)

    @hero.on_hit
    def hit(event: Event[Sprite, Collision]) -> None:
        raise LookupError("collision failure")

    monkeypatch.setattr(_collisions, "_MAX_CONTACTS", 1)
    with pytest.raises(StageError, match="8192"):
        tick(arena)
    monkeypatch.setattr(_collisions, "_MAX_CONTACTS", 8192)
    with pytest.raises(LookupError, match="collision failure"):
        tick(arena)
    close(arena)
    assert not arena._hit_contacts and not arena._hit_handlers


def test_sleeping_contact_and_shape_replacement_keep_episode(arena: Stage) -> None:
    from plocks import Box

    arena.physics.gravity = (0, -900)
    assert arena.physics._space is not None
    arena.physics._space.sleep_time_threshold = 0.05
    hero = Sprite(Image.rectangle(10, 10), y=20)
    floor = Sprite(Image.rectangle(100, 10), body_type=BodyType.STATIC)
    arena.add(hero)
    arena.add(floor)
    hero.body.rotation_locked = True
    hits: list[Collision] = []

    @hero.on_hit
    def hit(event: Event[Sprite, Collision]) -> None:
        hits.append(event.data)

    tick(arena, 180)
    assert len(hits) == 1
    hero.body.shape = Box(12, 10)
    tick(arena, 180)
    assert len(hits) == 1


def test_new_handler_snapshot_and_immutable_payload(arena: Stage) -> None:
    from dataclasses import FrozenInstanceError

    a = Sprite(Image.rectangle(10, 10), body_type=BodyType.KINEMATIC)
    b = Sprite(a.image, x=10, body_type=BodyType.STATIC)
    arena.add(a)
    arena.add(b)
    observed: list[Collision] = []
    late: list[Collision] = []

    def later(event: Event[Sprite, Collision]) -> None:
        late.append(event.data)

    @a.on_hit
    def hit(event: Event[Sprite, Collision]) -> None:
        observed.append(event.data)
        a.on_hit(later)

    tick(arena, 4)
    assert len(observed) == 1 and not late
    attribute = "point"
    with pytest.raises(FrozenInstanceError):
        setattr(observed[0], attribute, (0, 0))
    a.position = (-20, 0)
    tick(arena)
    a.position = (0, 0)
    tick(arena)
    assert len(observed) == 2 and len(late) == 1


def test_callback_failure_in_driver_closes_everything() -> None:
    stage = Stage(physics=True)
    a = Sprite(Image.rectangle(10, 10), body_type=BodyType.KINEMATIC)
    b = Sprite(a.image, x=10, body_type=BodyType.STATIC)
    stage.add(a)
    stage.add(b)
    body = a.body

    @a.on_hit
    def failure(event: Event[Sprite, Collision]) -> None:
        raise LookupError("physical callback failed")

    with pytest.raises(LookupError, match="physical callback failed"):
        stage.run()
    assert stage._state == "closed" and not stage.objects
    assert not stage._hit_contacts and not stage._hit_handlers
    assert body._native is None and a._stage is None


def test_approved_collision_ownership_inventory() -> None:
    from dataclasses import fields

    import plocks
    from plocks import Body, Puppet

    assert "Collision" in plocks.__all__
    assert {field.name for field in fields(Collision)} == {"target", "point", "normal", "cell"}
    assert "_hit_contacts" in Stage.__slots__
    assert not any("contact" in field for field in Body.__slots__)
    assert not any("contact" in field for field in Sprite.__slots__)
    assert not any("contact" in field for field in Puppet.__slots__)


def test_circle_collider_uses_surface_point_not_picture_rectangle(arena: Stage) -> None:
    from plocks import Circle

    hero = Sprite(Image.rectangle(40, 40), x=10)
    target = Sprite(hero.image, x=20, body_type=BodyType.STATIC)
    arena.add(hero)
    arena.add(target)
    hero.body.shape = target.body.shape = Circle(5)
    hero.body.rotation_locked = True
    hits: list[Collision] = []

    @hero.on_hit
    def collision(event: Event[Sprite, Collision]) -> None:
        hits.append(event.data)

    tick(arena)
    assert len(hits) == 1
    assert hits[0].point == pytest.approx((15, 0))
    assert hits[0].normal == pytest.approx((-1, 0))


def test_pause_inside_hit_stops_remaining_batch_and_visual_phase(arena: Stage) -> None:
    hero = Sprite(Image.rectangle(10, 10), body_type=BodyType.KINEMATIC)
    left = Sprite(hero.image, x=-8, body_type=BodyType.STATIC)
    right = Sprite(hero.image, x=8, body_type=BodyType.STATIC)
    for obj in (hero, left, right):
        arena.add(obj)
    hit_events: list[object] = []
    touch_events: list[object] = []

    @hero.on_hit
    def hit(event: Event[Sprite, Collision]) -> None:
        hit_events.append(event.data.target)
        arena.pause()

    @hero.on_touch(left)
    def touched(event: Event[Sprite, Sprite]) -> None:
        touch_events.append(event.data)

    tick(arena)
    assert hit_events == [left] and not touch_events and arena.paused
    tick(arena, 20)
    assert hit_events == [left] and not touch_events
    arena.resume()
    tick(arena, 3)
    assert hit_events == [left] and touch_events == [left]
