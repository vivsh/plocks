"""Ordinary solid tile collision under continuously held movement."""

import pytest

from plocks import Collision, Event, GamepadButton, GamepadInput, Image, Sprite, Stage, TileMap
from plocks._gamepads import _apply
from plocks._runtime import advance, close
from plocks.physics import _native


@pytest.mark.parametrize("movement", ["walk", "velocity"])
def test_falling_actor_cannot_be_driven_into_solid_wall(movement: str) -> None:
    """Repeated left input keeps a dynamic actor outside terrain and reports contact."""
    stage = Stage(physics=True)
    tile = Image.rectangle(40, 40)
    wall = TileMap(["#"] * 20, {"#": tile}, tile_size=(40, 40), solid={"#"}, x=0, y=400)
    hero = Sprite(Image.rectangle(30, 40), x=65, y=200)
    stage.add(wall)
    stage.add(hero)
    hero.body.rotation_locked = True
    hits: list[Collision] = []

    @hero.on_button_down(GamepadButton.LEFT, gamepad=stage.gamepads[0], repeat=0.01)
    def left(event: Event[Sprite, object]) -> None:
        body = event.target.body
        if movement == "walk":
            body.walk(speed=-200)
        else:
            body.velocity = (-200, 0)

    @hero.on_hit
    def hit(event: Event[Sprite, Collision]) -> None:
        hits.append(event.data)

    stage._state, stage._last_wall = "running", 0.0
    _apply(stage.gamepads[0], GamepadInput(buttons=frozenset({GamepadButton.LEFT})))
    try:
        for _ in range(60):
            advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)
            shape = next(iter(_native(hero.body).shapes))
            assert shape.cache_bb().left >= 39.85
        assert any(hit.target is wall for hit in hits)
    finally:
        close(stage)


@pytest.mark.parametrize("speed,width", [(200, 40), (1200, 40), (6000, 40), (12000, 40), (6000, 1)])
@pytest.mark.parametrize("side", ["left", "right"])
@pytest.mark.parametrize("circle", [False, True])
def test_fast_held_movement_stays_outside_wall(
    speed: float, width: int, side: str, circle: bool
) -> None:
    """Both round and rectangular bodies remain outside narrow or ordinary tile walls."""
    from plocks import Circle

    stage = Stage(physics=True)
    image = Image.rectangle(width, 40)
    wall = TileMap(["#"] * 20, {"#": image}, tile_size=(width, 40), solid={"#"}, x=0, y=400)
    hero = Sprite(Image.rectangle(30, 30), x=width + 25 if side == "right" else -25, y=200)
    stage.add(wall)
    stage.add(hero)
    hero.body.rotation_locked = True
    if circle:
        hero.body.shape = Circle(15)
    stage._state, stage._last_wall = "running", 0.0
    try:
        for _ in range(8):
            hero.body.walk(speed=-speed if side == "right" else speed)
            advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)
            bounds = next(iter(_native(hero.body).shapes)).cache_bb()
            if side == "right":
                assert bounds.left >= width - 0.15
            else:
                assert bounds.right <= 0.15
    finally:
        close(stage)


def test_solid_tile_budget_rejects_before_stepping() -> None:
    """Unsafe solid-terrain speeds fail before position or simulated time changes."""
    from plocks import PhysicsError

    stage = Stage(physics=True)
    image = Image.rectangle(1, 40)
    wall = TileMap(["#"], {"#": image}, tile_size=(1, 40), solid={"#"})
    hero = Sprite(Image.rectangle(20, 20), x=50)
    stage.add(wall)
    stage.add(hero)
    hero.body.velocity = (-1e8, 0)
    stage._state, stage._last_wall = "running", 0.0
    try:
        before, before_time = hero.position, stage.time
        with pytest.raises(PhysicsError, match="1024 physics substeps"):
            advance(stage, 1 / stage.tick_rate)
        assert hero.position == before and stage.time == before_time
    finally:
        close(stage)


def test_swept_projectile_does_not_increase_solid_only_substep_count() -> None:
    """A fast sensor projectile retains swept hits without forcing extra terrain steps."""
    from plocks import BodyType
    from plocks._physics import _substeps

    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    image = Image.rectangle(40, 40)
    wall = TileMap(["#"], {"#": image}, tile_size=(40, 40), solid={"#"}, x=0, y=20)
    hero = Sprite(image, x=150)
    bullet = Sprite(Image.circle(2), x=-100, body_type=BodyType.KINEMATIC)
    for actor in (wall, hero, bullet):
        stage.add(actor)
    bullet.body.projectile = True
    bullet.body.velocity = (12000, 0)
    hits: list[Collision] = []

    @bullet.on_hit
    def hit(event: Event[Sprite, Collision]) -> None:
        hits.append(event.data)

    stage._state, stage._last_wall = "running", 0.0
    try:
        assert _substeps(stage.physics, 1 / stage.tick_rate, ()) == 4
        advance(stage, 1 / stage.tick_rate)
        assert len(hits) == 1 and hits[0].target is wall
        assert bullet.body.velocity == (0, 0)
    finally:
        close(stage)


def test_wall_sliding_continues_with_zero_friction() -> None:
    """An airborne zero-friction character keeps falling while pressing into a wall."""
    stage = Stage(physics=True)
    tile = Image.rectangle(40, 40)
    wall = TileMap(["#"] * 20, {"#": tile}, tile_size=(40, 40), solid={"#"}, x=0, y=400)
    hero = Sprite(Image.rectangle(30, 40), x=65, y=200)
    stage.add(wall)
    stage.add(hero)
    hero.body.rotation_locked = True
    hero.body.friction = 0
    stage._state, stage._last_wall = "running", 0.0
    try:
        for _ in range(30):
            hero.body.walk(speed=-200)
            advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)
            assert next(iter(_native(hero.body).shapes)).cache_bb().left >= 39.85
        assert hero.y < 120
    finally:
        close(stage)


@pytest.mark.parametrize("speed", [600, 6000, 12000])
def test_fast_fall_lands_on_solid_floor(speed: float) -> None:
    """High-speed downward motion lands on ordinary solid terrain without tunneling."""
    stage = Stage(physics=True)
    image = Image.rectangle(40, 10)
    floor = TileMap(["#####"], {"#": image}, tile_size=(40, 10), solid={"#"}, x=-100, y=0)
    hero = Sprite(Image.rectangle(20, 20), y=60)
    stage.add(floor)
    stage.add(hero)
    hero.body.rotation_locked = True
    hero.body.velocity = (0, -speed)
    stage._state, stage._last_wall = "running", 0.0
    try:
        for _ in range(15):
            advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)
            assert next(iter(_native(hero.body).shapes)).cache_bb().bottom >= -0.15
        assert hero.body.grounded
    finally:
        close(stage)


def test_tile_edit_opens_wall_and_restores_blocking() -> None:
    """Rebuilt solid geometry permits passage after deletion and blocks when restored."""
    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    image = Image.rectangle(40, 40)
    wall = TileMap(["#"], {"#": image}, tile_size=(40, 40), solid={"#"}, x=0, y=20)
    hero = Sprite(Image.rectangle(20, 20), x=55)
    stage.add(wall)
    stage.add(hero)
    hero.body.rotation_locked = True
    stage._state, stage._last_wall = "running", 0.0
    try:
        for _ in range(12):
            hero.body.walk(speed=-200)
            advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)
        assert hero.x >= 49.85
        wall.set_tile(row=0, column=0, tile=None)
        for _ in range(30):
            hero.body.walk(speed=-200)
            advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)
        assert hero.x < -20
        wall.set_tile(row=0, column=0, tile="#")
        for _ in range(30):
            hero.body.walk(speed=200)
            advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)
        assert hero.x <= -9.85
    finally:
        close(stage)


@pytest.mark.parametrize("filter_mode", ["sensor", "group"])
def test_sensors_and_excluded_terrain_still_pass_through(filter_mode: str) -> None:
    """Solid terrain does not block an actor that explicitly opts out of collision."""
    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    image = Image.rectangle(40, 40)
    wall = TileMap(["#"], {"#": image}, tile_size=(40, 40), solid={"#"}, x=0, y=20)
    hero = Sprite(Image.rectangle(20, 20), x=55)
    stage.add(wall)
    stage.add(hero)
    if filter_mode == "sensor":
        hero.body.sensor = True
    else:
        hero.body.collides_with = set()
    stage._state, stage._last_wall = "running", 0.0
    try:
        hero.body.velocity = (-600, 0)
        for _ in range(15):
            advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)
        assert hero.x < -20
    finally:
        close(stage)


def test_adaptive_steps_follow_actual_tile_edits() -> None:
    """Empty terrain does not impose a speed budget until a solid cell is added."""
    from plocks import PhysicsError
    from plocks._physics import _substeps

    stage = Stage(physics=True)
    image = Image.rectangle(1, 40)
    wall = TileMap(["."], {"#": image}, tile_size=(1, 40), solid={"#"})
    hero = Sprite(Image.rectangle(20, 20), x=50)
    stage.add(wall)
    stage.add(hero)
    hero.body.velocity = (-1e8, 0)
    try:
        assert _substeps(stage.physics, 1 / stage.tick_rate, ()) == 4
        wall.set_tile(row=0, column=0, tile="#")
        with pytest.raises(PhysicsError, match="1024 physics substeps"):
            _substeps(stage.physics, 1 / stage.tick_rate, ())
        wall.set_tile(row=0, column=0, tile=None)
        assert _substeps(stage.physics, 1 / stage.tick_rate, ()) == 4
    finally:
        close(stage)


def test_stacked_sprites_rest_on_solid_terrain() -> None:
    """The world correction setting preserves stable ordinary stacked contacts."""
    stage = Stage(physics=True)
    image = Image.rectangle(40, 20)
    floor = TileMap(["#####"], {"#": image}, tile_size=(40, 20), solid={"#"}, x=-100, y=0)
    lower = Sprite(Image.rectangle(20, 20), y=35)
    upper = Sprite(lower.image, y=65)
    for actor in (floor, lower, upper):
        stage.add(actor)
    lower.body.rotation_locked = upper.body.rotation_locked = True
    stage._state, stage._last_wall = "running", 0.0
    try:
        for _ in range(180):
            advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)
        assert lower.y == pytest.approx(10, abs=0.25)
        assert upper.y == pytest.approx(30, abs=0.3)
        assert lower.body.grounded and upper.body.grounded
    finally:
        close(stage)


def test_bounce_remains_effective_against_solid_terrain() -> None:
    """Zero correction bias does not suppress the solver's restitution response."""
    stage = Stage(physics=True)
    image = Image.rectangle(40, 20)
    floor = TileMap(["#####"], {"#": image}, tile_size=(40, 20), solid={"#"}, x=-100, y=0)
    hero = Sprite(Image.rectangle(20, 20), y=50)
    stage.add(floor)
    stage.add(hero)
    # Pymunk combines material restitution; give both surfaces nonzero bounce.
    hero.body.bounce = 1
    for terrain in stage.physics._terrain:
        if terrain.native is not None:
            for shape in terrain.native.shapes:
                shape.elasticity = 1
    hero.body.rotation_locked = True
    stage._state, stage._last_wall = "running", 0.0
    try:
        bounced = False
        for _ in range(60):
            advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)
            bounced |= hero.body.velocity[1] > 100
        assert bounced
    finally:
        close(stage)


def test_corner_contact_stays_outside_wall_and_floor() -> None:
    """Held left input at a floor-wall corner never drives the body into either tile."""
    stage = Stage(physics=True)
    image = Image.rectangle(40, 40)
    terrain = TileMap(
        ["#.....", "#.....", "######"],
        {"#": image},
        tile_size=(40, 40),
        solid={"#"},
        x=0,
        y=120,
    )
    hero = Sprite(Image.rectangle(20, 20), x=60, y=90)
    stage.add(terrain)
    stage.add(hero)
    hero.body.rotation_locked = True
    hero.body.friction = 0
    stage._state, stage._last_wall = "running", 0.0
    try:
        for _ in range(120):
            hero.body.walk(speed=-200)
            advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)
            bounds = next(iter(_native(hero.body).shapes)).cache_bb()
            assert bounds.left >= 39.85 and bounds.bottom >= 39.85
        assert hero.body.grounded
    finally:
        close(stage)


def test_initial_overlap_is_corrected_without_extra_owner_state() -> None:
    """The native solver resolves an initially overlapping dynamic body against a tile."""
    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    image = Image.rectangle(40, 40)
    wall = TileMap(["#"], {"#": image}, tile_size=(40, 40), solid={"#"}, x=0, y=20)
    hero = Sprite(Image.rectangle(20, 20), x=35)
    stage.add(wall)
    stage.add(hero)
    hero.body.rotation_locked = True
    stage._state, stage._last_wall = "running", 0.0
    try:
        advance(stage, 1 / stage.tick_rate)
        bounds = next(iter(_native(hero.body).shapes)).cache_bb()
        assert bounds.left >= 39.85
    finally:
        close(stage)


def test_fast_projectile_still_hits_moving_dynamic_target_in_solid_world() -> None:
    """Excluding swept speed from tile-only stepping retains relative-motion hits."""
    from plocks import BodyType
    from plocks._physics import _substeps

    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    image = Image.rectangle(40, 40)
    wall = TileMap(["#"], {"#": image}, tile_size=(40, 40), solid={"#"}, x=-200, y=20)
    target = Sprite(image, x=100, y=20)
    bullet = Sprite(Image.circle(2), body_type=BodyType.KINEMATIC)
    for actor in (wall, target, bullet):
        stage.add(actor)
    target.body.velocity = (0, -100)
    bullet.body.projectile = True
    bullet.body.velocity = (12000, 0)
    hits: list[Collision] = []

    @bullet.on_hit
    def hit(event: Event[Sprite, Collision]) -> None:
        hits.append(event.data)

    stage._state, stage._last_wall = "running", 0.0
    try:
        assert _substeps(stage.physics, 1 / stage.tick_rate, ()) == 4
        advance(stage, 1 / stage.tick_rate)
        assert len(hits) == 1 and hits[0].target is target
    finally:
        close(stage)


@pytest.mark.parametrize("tick_rate", [30, 120])
def test_fast_wall_movement_at_different_tick_rates(tick_rate: int) -> None:
    """Adaptive terrain steps use the actual fixed tick duration."""
    stage = Stage(physics=True, tick_rate=tick_rate)
    image = Image.rectangle(40, 40)
    wall = TileMap(["#"] * 20, {"#": image}, tile_size=(40, 40), solid={"#"}, x=0, y=400)
    hero = Sprite(Image.rectangle(30, 40), x=65, y=200)
    stage.add(wall)
    stage.add(hero)
    hero.body.rotation_locked = True
    stage._state, stage._last_wall = "running", 0.0
    try:
        for _ in range(8):
            hero.body.walk(speed=-6000)
            advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)
            assert next(iter(_native(hero.body).shapes)).cache_bb().left >= 39.85
    finally:
        close(stage)
