"""Remove level clones and tile maps without discarding original actors or callbacks."""

from plocks import BodyType, Event, Image, Puppet, Sprite, Stage, TileMap
from plocks._runtime import advance, close


def tick(stage: Stage) -> None:
    advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)


def test_remove_clones_preserves_originals_and_their_callbacks() -> None:
    """All attached Sprite/Puppet copies go; original and Stage callbacks keep running."""
    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    original = Sprite(Image.rectangle(10, 10), x=-100)
    person = Puppet.stick_figure()
    person.position = (100, 0)
    stage.add(original)
    stage.add(person)
    calls: list[str] = []

    @stage.on_update
    def stage_update(event: Event[Stage, float]) -> None:
        calls.append("stage")

    @original.on_update
    def sprite_update(event: Event[Sprite, float]) -> None:
        calls.append("sprite")

    @person.on_update
    def puppet_update(event: Event[Puppet, float]) -> None:
        calls.append("puppet")

    sprite_clone = original.clone()
    descendant = sprite_clone.clone()
    puppet_clone = person.clone()
    sprite_clone.position = (-200, 0)
    descendant.position = (-300, 0)
    puppet_clone.position = (200, 0)
    stage._state, stage._last_wall = "running", 0.0
    try:
        stage.remove_clones()
        assert stage.clone_count == 0
        assert original in stage.objects and person in stage.objects
        assert all(actor._stage is None for actor in (sprite_clone, descendant, puppet_clone))
        tick(stage)
        assert calls == ["stage", "sprite", "puppet"]
        stage.remove_clones()
        tick(stage)
        assert calls == ["stage", "sprite", "puppet"] * 2
    finally:
        close(stage)


def test_remove_clones_honors_end_callbacks_and_snapshot() -> None:
    """Clone-end handlers can remove a peer or spawn a replacement without recursion."""
    stage = Stage()
    original = Sprite(Image.rectangle(10, 10))
    stage.add(original)
    removed: list[Sprite] = []
    replacements: list[Sprite] = []

    @original.on_clone_end
    def ended(event: Event[Sprite, None]) -> None:
        removed.append(event.target)
        if event.target is first:
            second.remove()
            replacements.append(original.clone())

    first = original.clone()
    second = original.clone()
    stage._state, stage._last_wall = "running", 0.0
    try:
        stage.remove_clones()
        assert removed == [first, second]
        assert len(replacements) == 1 and replacements[0] in stage.objects
        assert stage.clone_count == 1 and original in stage.objects
    finally:
        close(stage)


def test_remove_tilemap_detaches_terrain_and_keeps_sprites_and_handlers() -> None:
    """Tile maps leave physics and can be re-added; existing sprite callbacks survive."""
    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    image = Image.rectangle(40, 40)
    wall = TileMap(["#"], {"#": image}, tile_size=(40, 40), solid={"#"}, x=0, y=20)
    other_map = TileMap(["#"], {"#": image}, tile_size=(40, 40), solid={"#"}, x=200, y=20)
    hero = Sprite(Image.rectangle(10, 10), x=-50)
    for obj in (wall, other_map, hero):
        stage.add(obj)
    seen: list[Sprite] = []

    @hero.on_update
    def update(event: Event[Sprite, float]) -> None:
        seen.append(event.target)

    stage._state, stage._last_wall = "running", 0.0
    try:
        assert not hero.body.can_travel(distance=100, direction=90)
        stage.remove(wall)
        stage.remove(other_map)
        assert wall not in stage.objects and other_map not in stage.objects
        assert not stage.physics._terrain and hero.body.can_travel(distance=100, direction=90)
        tick(stage)
        assert seen == [hero] and wall.get_tile(row=0, column=0) == "#"
        stage.add(wall)
        assert not hero.body.can_travel(distance=100, direction=90)
        stage.remove(wall)
        assert hero in stage.objects
    finally:
        close(stage)


def test_level_switch_from_button_keeps_window_stage_and_decorators() -> None:
    """A callback replaces terrain and clones while later inputs still reach the hero."""
    from plocks import GamepadButton, GamepadInput, GamepadPress
    from plocks._gamepads import _apply

    stage = Stage(physics=True)
    image = Image.rectangle(20, 20)
    old_map = TileMap(["#"], {"#": image}, tile_size=(20, 20), solid={"#"}, x=-100)
    new_map = TileMap(["##"], {"#": image}, tile_size=(20, 20), solid={"#"}, x=100)
    hero = Sprite(image)
    enemy = Sprite(image, x=200)
    for obj in (old_map, hero, enemy):
        stage.add(obj)
    enemy.clone()
    calls: list[str] = []

    @hero.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])
    def next_level(event: Event[Sprite, GamepadPress]) -> None:
        calls.append("button")
        if old_map in stage.objects:
            stage.remove_clones()
            stage.remove(old_map)
            stage.add(new_map)

    stage._state, stage._last_wall = "running", 0.0
    space = stage.physics._space
    try:
        _apply(stage.gamepads[0], GamepadInput(buttons=frozenset({GamepadButton.A})))
        tick(stage)
        assert old_map not in stage.objects and new_map in stage.objects
        assert hero in stage.objects and enemy in stage.objects and stage.clone_count == 0
        assert stage.physics._space is space
        _apply(stage.gamepads[0], GamepadInput())
        tick(stage)
        _apply(stage.gamepads[0], GamepadInput(buttons=frozenset({GamepadButton.A})))
        tick(stage)
        assert calls == ["button", "button"]
    finally:
        close(stage)


def test_removing_a_tilemap_does_not_rewrite_its_edited_cells() -> None:
    """Detach removes visual membership and terrain, not the map's own edits."""
    stage = Stage(physics=True)
    image = Image.rectangle(40, 40)
    world = TileMap(["##"], {"#": image}, tile_size=(40, 40), solid={"#"}, x=0, y=20)
    stage.add(world)
    try:
        world.set_tile(row=0, column=0, tile=None)
        stage.remove(world)
        assert world not in stage.objects and not stage.physics._terrain
        assert world.cells == ((None, "#"),)
        stage.add(world)
        assert stage.physics.raycast(start=(20, 50), end=(20, 0)) is None
        hit = stage.physics.raycast(start=(60, 50), end=(60, 0))
        assert hit is not None and hit.target is world and hit.cell == (0, 1)
    finally:
        close(stage)


def test_touch_decorator_survives_resetting_and_readding_the_same_map() -> None:
    """A detached reset restores terrain on re-add and preserves the map-specific callback."""
    stage = Stage(physics=True)
    image = Image.rectangle(40, 40)
    world = TileMap(["#"], {"#": image}, tile_size=(40, 40), solid={"#"}, x=-20, y=20)
    hero = Sprite(Image.rectangle(10, 10), body_type=BodyType.NONE)
    stage.add(world)
    stage.add(hero)
    hits: list[TileMap] = []

    @hero.on_touch(world)
    def touching(event: Event[Sprite, TileMap]) -> None:
        hits.append(event.data)

    stage._state, stage._last_wall = "running", 0.0
    try:
        tick(stage)
        world.set_tile(row=0, column=0, tile=None)
        stage.remove(world)
        tick(stage)
        world.reset_tiles()
        assert world.cells == (("#",),) and not stage.physics._terrain
        stage.add(world)
        hit = stage.physics.raycast(start=(0, 40), end=(0, 0))
        assert hit is not None and hit.target is world and hit.cell == (0, 0)
        tick(stage)
        assert hits == [world, world]
    finally:
        close(stage)


def test_repeated_new_levels_have_fresh_tiles_and_collision_events() -> None:
    """A surviving actor can hit a new map at the same position in every level."""
    from plocks import Collision

    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    image = Image.rectangle(40, 40)
    hero = Sprite(Image.rectangle(10, 10), x=-50)
    stage.add(hero)
    hero.body.rotation_locked = True
    hits: list[Collision] = []

    @hero.on_hit
    def hit(event: Event[Sprite, Collision]) -> None:
        hits.append(event.data)

    stage._state, stage._last_wall = "running", 0.0
    try:
        for number in range(10):
            level = TileMap(["#"], {"#": image}, tile_size=(40, 40), solid={"#"}, x=0, y=20)
            stage.add(level)
            hero.position = (-50, 0)
            hero.body.velocity = (400, 0)
            for _ in range(15):
                tick(stage)
            assert len(hits) == number + 1
            assert hits[-1].target is level and hits[-1].cell == (0, 0)
            level.set_tile(row=0, column=0, tile=None)
            stage.remove(level)
            assert not stage.physics._terrain
    finally:
        close(stage)
