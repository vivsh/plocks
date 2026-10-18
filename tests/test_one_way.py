"""One-way contact admission uses the ordinary driver and native pair lifetime."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from plocks import (
    BodyType,
    Bounds,
    Box,
    Canvas,
    Circle,
    Costume,
    Event,
    PhysicsError,
    Puppet,
    Sprite,
    Stage,
    TileMap,
)
from plocks._runtime import advance, close

ASSETS = Path(__file__).parents[1] / "src/plocks/_games/platformer/assets"


def test_two_actors_jump_and_land_independently_through_the_shared_driver() -> None:
    """One rider stays supported while another jumps through, clears, and lands."""
    stage = Stage(background="skyblue", physics=True)
    platform = Sprite(ASSETS / "platform.png", one_way=True, body_type=BodyType.STATIC)
    stage.add(platform)
    platform.body.shape = Box(160, 16)
    costume = Costume(ASSETS / "hero.png").resized(12, 20)
    rider = Sprite(costume, x=-30, y=18)
    jumper = Sprite(costume, x=30, y=-40)
    stage.add(rider)
    stage.add(jumper)
    rider.body.rotation_locked = jumper.body.rotation_locked = True
    jumper.body.velocity = (0, 420)
    maximum = jumper.y
    supported_while_passing = False
    draws = 0

    @stage.on_update
    def inspect(event: Event[Stage, float]) -> None:
        nonlocal maximum, supported_while_passing
        maximum = max(maximum, jumper.y)
        if jumper.y < 18 and stage.time > 0.02:
            supported_while_passing |= rider.body.grounded
        if stage.time >= 1.3:
            assert maximum > 40 and supported_while_passing
            assert rider.y == pytest.approx(18, abs=0.3) and rider.body.grounded
            assert jumper.y == pytest.approx(18, abs=0.3) and jumper.body.grounded
            assert rider.body.touching(platform.body) and jumper.body.touching(platform.body)
            stage.stop()

    @stage.on_draw
    def draw(canvas: Canvas) -> None:
        nonlocal draws
        canvas.text("Jump through; land on top", (-160, 120))
        draws += 1

    stage.run()
    assert draws > 20 and not stage.objects and stage.physics._space is None
    assert rider._stage is None and jumper._stage is None and platform._stage is None


@pytest.fixture
def scene() -> Iterator[Stage]:
    """Give each geometry test its own physics owner and always retire native resources."""
    stage = Stage(physics=True)
    stage._state = "running"
    stage._last_wall = 0
    try:
        yield stage
    finally:
        close(stage)


def ticks(stage: Stage, count: int) -> None:
    """Use the production fixed-step ordering with a synthetic wall clock."""
    now = stage._last_wall or 0
    for _ in range(count):
        now += 1 / stage.tick_rate
        advance(stage, now)


def platform(stage: Stage, *, moving: bool = False) -> Sprite:
    """Create the same 160-wide horizontal landing edge for Sprite tests."""
    role = BodyType.KINEMATIC if moving else BodyType.STATIC
    actor = Sprite(ASSETS / "platform.png", one_way=True, body_type=role)
    stage.add(actor)
    actor.body.shape = Box(160, 16)
    return actor


def rider(stage: Stage, *, x: float = 0, y: float = 60) -> Sprite:
    """Use a fixed 12-by-20 collider so expected feet heights are explicit."""
    actor = Sprite(Costume(ASSETS / "hero.png").resized(12, 20), x=x, y=y)
    stage.add(actor)
    actor.body.rotation_locked = True
    return actor


def tiles(stage: Stage) -> TileMap:
    """Build a five-cell one-way row whose top matches the Sprite platform."""
    world = TileMap(
        ["PPPPP"], {"P": ASSETS / "platform.png"}, tile_size=(32, 16), one_way={"P"}, x=-80, y=8
    )
    stage.add(world)
    return world


@pytest.mark.parametrize("kind", ["sprite", "tiles"])
def test_pass_from_below_then_land_with_independent_support(kind: str, scene: Stage) -> None:
    """Both constructors provide the same pair-specific jump-through/landing behavior."""
    surface = platform(scene) if kind == "sprite" else tiles(scene)
    above = rider(scene, x=-30, y=18)
    below = rider(scene, x=30, y=-40)
    below.body.velocity = (0, 420)
    maximum = below.y
    for _ in range(90):
        ticks(scene, 1)
        maximum = max(maximum, below.y)
        assert above.body.grounded
    assert maximum > 40 and below.body.grounded
    assert above.y == pytest.approx(18, abs=0.3)
    assert below.y == pytest.approx(18, abs=0.3)
    assert below.body.touching(surface.body if isinstance(surface, Sprite) else surface)


@pytest.mark.parametrize("kind", ["sprite", "tiles"])
def test_short_jump_reversal_does_not_catch_an_actor_inside(kind: str, scene: Stage) -> None:
    """Native rejection survives velocity reversal until that pair separates."""
    surface = platform(scene) if kind == "sprite" else tiles(scene)
    hero = rider(scene, y=-5)
    hero.body.velocity = (0, 80)
    ticks(scene, 5)
    assert hero.touching(surface) and not hero.body.grounded
    assert not hero.body.touching(surface.body if isinstance(surface, Sprite) else surface)
    ticks(scene, 40)
    assert hero.y < -100 and not hero.body.grounded


@pytest.mark.parametrize("kind", ["sprite", "tiles"])
def test_side_entry_passes_without_sideways_or_vertical_response(kind: str, scene: Stage) -> None:
    """A rider overlapping the landing height from the side is never pushed by the artwork."""
    if kind == "sprite":
        platform(scene)
    else:
        tiles(scene)
    scene.physics.gravity = (0, 0)
    hero = rider(scene, x=-130, y=3)
    hero.body.velocity = (200, 0)
    ticks(scene, 90)
    assert hero.x == pytest.approx(170) and hero.y == pytest.approx(3)
    assert hero.body.velocity == pytest.approx((200, 0)) and not hero.body.grounded


@pytest.mark.parametrize("kind", ["sprite", "tiles"])
def test_walking_off_the_edge_falls_without_a_hidden_wall(kind: str, scene: Stage) -> None:
    """An existing top contact ends normally when a rider steps beyond its last edge."""
    if kind == "sprite":
        platform(scene)
    else:
        tiles(scene)
    hero = rider(scene, x=78, y=18)
    ticks(scene, 2)
    assert hero.body.grounded
    hero.body.velocity = (180, 0)
    ticks(scene, 30)
    assert hero.x > 100 and hero.y < -20 and not hero.body.grounded


@pytest.mark.parametrize("kind", ["box", "circle", "puppet"])
def test_different_rider_shapes_share_the_same_platform_rule(kind: str, scene: Stage) -> None:
    """One-way platforms support circles and articulated actors without actor-specific contacts."""
    surface = platform(scene)
    if kind == "puppet":
        actor: Sprite | Puppet = Puppet.stick_figure()
        actor.position = (0, 60)
        scene.add(actor)
        actor.body.shape = Box(12, 20)
    else:
        actor = rider(scene)
        if kind == "circle":
            actor.body.shape = Circle(10)
    actor.body.rotation_locked = True
    ticks(scene, 60)
    assert actor.y == pytest.approx(18, abs=0.3) and actor.body.grounded
    assert actor.body.touching(surface.body)


def test_moving_lift_carries_a_rider_up_down_and_sideways(scene: Stage) -> None:
    """Kinematic relative velocity and ordinary friction retain support through direction changes."""
    lift = platform(scene, moving=True)
    hero = rider(scene)
    ticks(scene, 60)
    starting_y = hero.y
    up = lift.glide_by(y=30, seconds=1)
    ticks(scene, 61)
    assert up.done and lift.y == pytest.approx(30)
    assert hero.y > starting_y + 20
    ticks(scene, 30)  # Let the rider's upward momentum settle after the lift stops.
    assert hero.y == pytest.approx(starting_y + 30, abs=0.4) and hero.body.grounded
    down = lift.glide_by(y=-30, seconds=1)
    ticks(scene, 62)
    assert down.done and hero.y == pytest.approx(starting_y, abs=0.4)
    assert hero.body.grounded
    sideways = lift.glide_by(x=60, seconds=1)
    ticks(scene, 62)
    assert sideways.done and hero.x > 40 and hero.body.grounded


def test_upward_moving_platform_can_be_jumped_through(scene: Stage) -> None:
    """A rising platform supports one actor without stopping a second actor's upward passage."""
    lift = platform(scene, moving=True)
    above = rider(scene, x=-30, y=18)
    below = rider(scene, x=30, y=-40)
    lift.body.velocity = (0, 30)
    below.body.velocity = (0, 450)
    cleared = False
    for _ in range(120):
        ticks(scene, 1)
        cleared |= below.y - 10 > lift.y + 8
        assert above.body.grounded
    assert cleared and below.body.grounded
    assert below.y == pytest.approx(lift.y + 18, abs=0.4)


def test_pause_freezes_platform_motion_and_resume_keeps_contacts(scene: Stage) -> None:
    """The feature uses the existing simulation clock, including user pause and resume baseline."""
    lift = platform(scene, moving=True)
    hero = rider(scene)
    ticks(scene, 60)
    lift.glide_by(y=30, seconds=1)
    ticks(scene, 20)
    scene.pause()
    before = scene.time, lift.position, hero.position
    ticks(scene, 120)
    assert (scene.time, lift.position, hero.position) == before
    scene.resume()
    ticks(scene, 80)
    assert hero.body.grounded and lift.y == pytest.approx(30)


def test_offset_anchors_and_scaled_replacement_keep_the_top_edge_correct(scene: Stage) -> None:
    """The native edge derives from the Box top, independent of visual anchors or image changes."""
    surface = Sprite(
        Costume(ASSETS / "platform.png", anchor=(0, 0)),
        x=-100,
        y=100,
        scale=2,
        one_way=True,
        body_type=BodyType.STATIC,
    )
    scene.add(surface)
    surface.body.shape = Box(100, 20, center=(50, -10))
    hero = rider(scene, y=160)
    ticks(scene, 60)
    assert hero.y == pytest.approx(110, abs=0.3)
    surface.body.shape = Box(100, 20, center=(50, -15))
    surface.costume = ASSETS / "hero.png"
    ticks(scene, 60)
    assert hero.y == pytest.approx(100, abs=0.3) and hero.body.grounded
    surface.scale = 1
    hero.position = (-50, 160)
    ticks(scene, 60)
    assert hero.y == pytest.approx(105, abs=0.3) and hero.body.grounded


def test_mixed_palette_preserves_full_solid_collision_below(scene: Stage) -> None:
    """A fully solid neighbor still blocks upward movement while a one-way tile does not."""
    world = TileMap(
        ["PG"],
        {"P": ASSETS / "platform.png", "G": ASSETS / "grass.png"},
        tile_size=(32, 16),
        solid={"G"},
        one_way={"P"},
        x=-32,
        y=8,
    )
    scene.add(world)
    through = rider(scene, x=-16, y=-30)
    blocked = rider(scene, x=16, y=-30)
    through.body.velocity = blocked.body.velocity = (0, 400)
    ticks(scene, 20)
    assert through.y > 20 and blocked.y < -15
    assert world.solid == frozenset({"G"}) and world.one_way == frozenset({"P"})
    assert world.tiles_touching(Bounds(-32, -8, 32, 8)) == ((0, 0), (0, 1))


def test_tile_edits_and_movement_retire_old_contact_resources(scene: Stage) -> None:
    """Editing/removing/relocating a one-way cell uses the existing atomic terrain replacement."""
    world = tiles(scene)
    hero = rider(scene)
    ticks(scene, 60)
    assert hero.body.grounded
    previous = scene.physics._terrain[0]
    world.set_tile(row=0, column=2, tile=None)
    assert previous.native is None and not hero.body.grounded
    ticks(scene, 20)
    assert hero.y < -20
    world.set_tile(row=0, column=2, tile="P")
    world.position = (world.x, 50)
    hero.position = (0, 100)
    hero.body.velocity = (0, 0)
    ticks(scene, 60)
    assert hero.y == pytest.approx(60, abs=0.3) and hero.body.grounded
    scene.remove(world)
    assert not hero.body.grounded and not scene.physics._terrain
    scene.add(world)
    ticks(scene, 2)
    assert hero.body.grounded


def test_cloned_platforms_keep_configuration_but_have_independent_bodies(scene: Stage) -> None:
    """Clones preserve one-way admission and physical shape without sharing contacts or resources."""
    source = platform(scene, moving=True)
    source.body.friction = 0.4
    copied = source.clone()
    copied.x = 200
    assert copied.one_way and copied.body is not source.body
    assert copied.body.shape == source.body.shape and copied.body.friction == 0.4
    first = rider(scene)
    second = rider(scene, x=200)
    ticks(scene, 60)
    assert first.body.grounded and second.body.grounded
    old = source.body
    scene.remove(source)
    assert not first.body.grounded and second.body.grounded
    with pytest.raises(PhysicsError):
        _ = old.velocity
    scene.add(source)
    source.body.shape = Box(160, 16)
    first.position = (0, 60)
    first.body.velocity = (0, 0)
    ticks(scene, 60)
    assert source.one_way and first.body.grounded


def test_configuration_snapshots_and_nonphysical_overlap_queries() -> None:
    """One-way metadata is immutable and geometric touching remains independent of physics."""
    keys = {"P"}
    world = TileMap(["P"], {"P": ASSETS / "platform.png"}, tile_size=(32, 16), one_way=keys)
    keys.clear()
    actor = Sprite(Costume(ASSETS / "hero.png").resized(12, 20), x=10, y=-10)
    assert world.one_way == frozenset({"P"}) and actor.touching(world)
    assert world.tiles_touching(actor.bounds) == ((0, 0),)
    stage = Stage()
    try:
        stage.add(world)
        stage.add(actor)
        with pytest.raises(PhysicsError):
            _ = actor.body
        assert actor.touching(world)
    finally:
        close(stage)


@pytest.mark.parametrize("kind", ["unknown", "overlap", "parallax"])
def test_invalid_tile_configuration_fails_clearly(kind: str) -> None:
    """Missing keys, contradictory collision roles and physical parallax are rejected."""
    palette = {"P": ASSETS / "platform.png"}
    if kind == "unknown":
        with pytest.raises(KeyError, match="one-way"):
            TileMap(["P"], palette, tile_size=(32, 16), one_way={"?"})
    elif kind == "overlap":
        with pytest.raises(ValueError, match="both"):
            TileMap(["P"], palette, tile_size=(32, 16), solid={"P"}, one_way={"P"})
    else:
        world = TileMap(["P"], palette, tile_size=(32, 16), one_way={"P"})
        with pytest.raises(ValueError):
            world.parallax = (0.5, 1)
        assert world.parallax == (1, 1)
        with pytest.raises(ValueError):
            TileMap(["P"], palette, tile_size=(32, 16), one_way={"P"}, parallax=(0.5, 1))


def test_physical_tile_limit_counts_one_way_cells_and_preserves_failed_edits(scene: Stage) -> None:
    """One-way edges share the existing 4096-cell budget with ordinary solid terrain."""
    world = TileMap(
        ["P" * 4096 + "."], {"P": ASSETS / "platform.png"}, tile_size=(8, 8), one_way={"P"}
    )
    scene.add(world)
    native = scene.physics._terrain[0].native
    with pytest.raises(PhysicsError, match="4096"):
        world.set_tile(row=0, column=4096, tile="P")
    assert world.get_tile(row=0, column=4096) is None
    assert scene.physics._terrain[0].native is native
    world.set_tile(row=0, column=0, tile=None)
    world.set_tile(row=0, column=4096, tile="P")
    assert world.get_tile(row=0, column=4096) == "P"


def test_invalid_sprite_configuration_and_mutations_are_atomic(scene: Stage) -> None:
    """A one-way platform cannot silently become a rotating, circular or dynamic collider."""
    from typing import cast

    with pytest.raises(TypeError, match="bool"):
        Sprite(ASSETS / "platform.png", body_type=BodyType.STATIC, one_way=cast(bool, 1))
    for role in (BodyType.DYNAMIC, BodyType.NONE):
        with pytest.raises(ValueError, match="static or kinematic"):
            Sprite(ASSETS / "platform.png", body_type=role, one_way=True)
    with pytest.raises(ValueError, match="horizontal"):
        Sprite(ASSETS / "platform.png", body_type=BodyType.STATIC, one_way=True, direction=0)
    actor = platform(scene, moving=True)
    shape = actor.body.shape
    with pytest.raises(PhysicsError, match="Box"):
        actor.body.shape = Circle(10)
    with pytest.raises(PhysicsError, match="horizontal"):
        actor.body.angular_velocity = 30
    with pytest.raises(PhysicsError, match="horizontal"):
        actor.direction = 0
    assert actor.body.shape is shape and actor.direction == 90
    assert actor.body.angular_velocity == 0
    scene.remove(actor)
    with pytest.raises(ValueError, match="static or kinematic"):
        actor.body_type = BodyType.DYNAMIC
    assert actor.body_type is BodyType.KINEMATIC and actor.one_way


@pytest.mark.parametrize("kind", ["sprite", "tiles"])
def test_respawn_on_top_does_not_inherit_an_ignored_overlap(kind: str, scene: Stage) -> None:
    """A deliberate vertical teleport starts fresh contacts instead of falling through a respawn."""
    if kind == "sprite":
        platform(scene)
    else:
        tiles(scene)
    hero = rider(scene, y=-5)
    hero.body.velocity = (0, 80)
    ticks(scene, 5)
    assert not hero.body.grounded
    hero.position = (0, 18)
    hero.body.velocity = (0, 0)
    ticks(scene, 30)
    assert hero.y == pytest.approx(18, abs=0.3) and hero.body.grounded


def test_horizontal_position_changes_preserve_current_support(scene: Stage) -> None:
    """Clearing stale respawn pairs must not discard an existing rider's lateral support."""
    platform(scene)
    hero = rider(scene)
    ticks(scene, 60)
    assert hero.body.grounded
    hero.x += 1
    assert hero.body.grounded
    ticks(scene, 1)
    assert hero.body.grounded


@pytest.mark.parametrize("kind", ["sprite", "tiles"])
def test_jump_from_supported_top_can_land_again(kind: str, scene: Stage) -> None:
    """An existing accepted pair releases on takeoff and admits a later landing."""
    if kind == "sprite":
        platform(scene)
    else:
        tiles(scene)
    hero = rider(scene)
    ticks(scene, 60)
    assert hero.body.grounded
    hero.body.impulse(y=350)
    ticks(scene, 10)
    assert hero.y > 40 and not hero.body.grounded
    ticks(scene, 90)
    assert hero.body.grounded and hero.y == pytest.approx(18, abs=0.3)


def test_stacked_rows_land_on_the_highest_cleared_platform(scene: Stage) -> None:
    """Each tile edge owns its own admission even when several belong to one terrain body."""
    world = TileMap(
        ["PPP", "...", "PPP"],
        {"P": ASSETS / "platform.png"},
        tile_size=(32, 16),
        one_way={"P"},
        x=-48,
        y=48,
    )
    scene.add(world)
    hero = rider(scene, y=-40)
    hero.body.velocity = (0, 550)
    maximum = hero.y
    for _ in range(120):
        ticks(scene, 1)
        maximum = max(maximum, hero.y)
    assert maximum > 100 and hero.body.grounded
    assert hero.y == pytest.approx(58, abs=0.3)


@pytest.mark.parametrize("speed", [-600.0, -200.0, 200.0, 600.0])
def test_circle_crosses_tile_seams_without_losing_support(speed: float, scene: Stage) -> None:
    """Joined top edges must behave like one floor rather than bumping at every cell."""
    world = TileMap(
        ["P" * 160],
        {"P": ASSETS / "platform.png"},
        tile_size=(16, 16),
        one_way={"P"},
        x=-1280,
        y=8,
    )
    scene.add(world)
    hero = rider(scene, x=-400 if speed > 0 else 400, y=18)
    hero.body.shape = Circle(10)
    ticks(scene, 30)
    for _ in range(120):
        hero.body.velocity = (speed, hero.body.velocity[1])
        ticks(scene, 1)
        assert hero.body.grounded
        assert hero.y == pytest.approx(18, abs=0.2)


@pytest.mark.parametrize("kind", ["sprite", "tiles"])
@pytest.mark.parametrize("circle", [False, True])
@pytest.mark.parametrize("height,speed", [(2, 1000), (2, 12000), (8, 3000), (20, 6000)])
def test_fast_small_riders_land_instead_of_tunneling(
    kind: str,
    circle: bool,
    height: int,
    speed: int,
    scene: Stage,
) -> None:
    """Native substeps account for collider size and travel, not only the public tick rate."""
    surface: Sprite | TileMap = platform(scene) if kind == "sprite" else tiles(scene)
    hero = Sprite(Costume(ASSETS / "hero.png").resized(12, height), y=80)
    scene.add(hero)
    hero.body.rotation_locked = True
    if circle:
        hero.body.shape = Circle(height / 2)
    hero.body.velocity = (0, -speed)
    ticks(scene, 60)
    assert hero.body.grounded
    assert hero.y == pytest.approx(8 + height / 2, abs=0.3)
    assert hero.body.touching(surface.body if isinstance(surface, Sprite) else surface)


@pytest.mark.parametrize("kind", ["sprite", "tiles"])
def test_fast_riders_still_pass_through_from_below(kind: str, scene: Stage) -> None:
    """Additional sampling must preserve native rejection of upward crossings."""
    if kind == "sprite":
        platform(scene)
    else:
        tiles(scene)
    hero = Sprite(Costume(ASSETS / "hero.png").resized(12, 2), y=-80)
    scene.add(hero)
    hero.body.rotation_locked = True
    hero.body.velocity = (0, 12000)
    ticks(scene, 1)
    assert hero.y > 100 and not hero.body.grounded


def test_seam_neighbors_preserve_real_gaps_after_editing(scene: Stage) -> None:
    """Rebuilding neighbor hints must not leave invisible support over an erased tile."""
    world = TileMap(
        ["PPPPPP"],
        {"P": ASSETS / "platform.png"},
        tile_size=(32, 16),
        one_way={"P"},
        x=-96,
        y=8,
    )
    scene.add(world)
    hero = rider(scene, x=0, y=18)
    hero.body.shape = Circle(6)
    hero.y = 14
    ticks(scene, 30)
    assert hero.body.grounded
    world.set_tile(row=0, column=2, tile=None)
    world.set_tile(row=0, column=3, tile=None)
    ticks(scene, 30)
    assert hero.y < -50 and not hero.body.grounded


@pytest.mark.parametrize("rate", [30, 120])
def test_precision_follows_configured_tick_rate(rate: int) -> None:
    """Changing the public update rate does not reintroduce the missed landing."""
    scene = Stage(physics=True, tick_rate=rate)
    scene._state, scene._last_wall = "running", 0
    try:
        platform(scene)
        hero = Sprite(Costume(ASSETS / "hero.png").resized(12, 2), y=80)
        scene.add(hero)
        hero.body.rotation_locked = True
        hero.body.velocity = (0, -6000)
        ticks(scene, rate)
        assert hero.body.grounded and hero.y == pytest.approx(9, abs=0.3)
    finally:
        close(scene)


def test_accelerating_small_rider_uses_force_aware_precision(scene: Stage) -> None:
    """A force starting from rest must not evade the size-aware travel calculation."""
    platform(scene)
    hero = Sprite(Costume(ASSETS / "hero.png").resized(12, 2), y=80)
    scene.add(hero)
    hero.body.rotation_locked = True
    hero.body.force(y=-200000, seconds=0.025)
    ticks(scene, 60)
    assert hero.body.grounded and hero.y == pytest.approx(9, abs=0.3)


def test_extreme_motion_fails_with_cleanup_instead_of_unbounded_work() -> None:
    """The work budget raises a useful error and the shared driver still releases resources."""
    scene = Stage(physics=True)
    platform(scene)
    hero = Sprite(Costume(ASSETS / "hero.png").resized(12, 2), y=80)
    scene.add(hero)
    hero.body.velocity = (0, -1e9)
    with pytest.raises(PhysicsError, match="1024 physics substeps.*reduce speed"):
        scene.run()
    assert scene._state == "closed" and scene.physics._space is None
    assert not scene.objects and hero._stage is None


@pytest.mark.parametrize("lift_speed,rider_speed", [(6000, 0), (-6000, -12000)])
def test_fast_moving_lift_uses_relative_travel(
    lift_speed: int,
    rider_speed: int,
    scene: Stage,
) -> None:
    """Precision includes the moving edge, both when it rises and when a rider catches it."""
    lift = platform(scene, moving=True)
    lift.y = -80
    lift.body.velocity = (0, lift_speed)
    hero = rider(scene, y=60)
    hero.body.velocity = (0, rider_speed)
    ticks(scene, 30)
    assert hero.body.grounded and hero.body.touching(lift.body)
    assert hero.y == pytest.approx(lift.y + 18, abs=0.3)
