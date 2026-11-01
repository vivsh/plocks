"""Cardinal cell stepping is centered, bounded, cooperative and collision-aware."""

from collections.abc import Iterator

import pytest

from plocks import BodyType, Image, PhysicsError, Script, Sprite, Stage, StageError, TileMap
from plocks._runtime import advance, close
from plocks._scripts import _step


def tick(stage: Stage, count: int = 1) -> None:
    for _ in range(count):
        advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)


@pytest.fixture
def arena() -> Iterator[tuple[Stage, TileMap]]:
    stage = Stage(physics=True)
    world = TileMap(
        [".....", "...#.", ".....", "....."],
        {"#": Image.rectangle(32, 24)},
        tile_size=(32, 24),
        solid={"#"},
        y=96,
    )
    stage.add(world)
    stage._state = "running"
    stage._last_wall = 0
    yield stage, world
    close(stage)


@pytest.mark.parametrize("physical", [False, True])
def test_centered_step_ignores_competition_and_blocks_tiles(
    arena: tuple[Stage, TileMap], physical: bool
) -> None:
    stage, world = arena
    actor = Sprite(
        Image.rectangle(10, 10), body_type=BodyType.KINEMATIC if physical else BodyType.NONE
    )
    actor.position = world.cell_center(row=1, column=1)
    stage.add(actor)
    first = actor.move_cell(world, direction=90)
    ignored = actor.move_cell(world, direction=180)
    _step(stage)
    assert ignored.done and not first.done
    tick(stage, 14)
    assert actor.position == world.cell_center(row=1, column=2) and first.done
    blocked = actor.move_cell(world, direction=90)
    tick(stage)
    assert blocked.done and actor.position == world.cell_center(row=1, column=2)
    actor.act(Script().move_cell(world, direction=180).move_cell(world, direction=270))
    tick(stage, 26)
    assert actor.position == world.cell_center(row=2, column=1)
    assert actor.direction == 90


def test_cardinals_non_square_cells_and_map_boundary(arena: tuple[Stage, TileMap]) -> None:
    stage, world = arena
    actor = Sprite(Image.rectangle(10, 10), body_type=BodyType.NONE)
    actor.position = world.cell_center(row=0, column=0)
    stage.add(actor)
    actor.move_cell(world, direction=270)
    tick(stage)
    assert actor.position == (16, 84)
    actor.act(
        Script()
        .move_cell(world, direction=450, seconds=0.025)
        .move_cell(world, direction=180, seconds=0.025)
        .move_cell(world, direction=270, seconds=0.025)
        .move_cell(world, direction=0, seconds=0.025)
    )
    tick(stage, 8)
    assert actor.position == (16, 84)
    with pytest.raises(ValueError):
        actor.move_cell(world, direction=45)
    with pytest.raises(ValueError):
        actor.move_cell(world, direction=90, seconds=0)


def test_cell_pause_cancel_and_off_center_rejection(arena: tuple[Stage, TileMap]) -> None:
    stage, world = arena
    actor = Sprite(Image.rectangle(10, 10), body_type=BodyType.NONE)
    actor.position = world.cell_center(row=1, column=1)
    stage.add(actor)
    action = actor.move_cell(world, direction=90)
    tick(stage, 4)
    position = actor.position
    stage.pause()
    tick(stage, 40)
    assert actor.position == position
    stage.resume()
    tick(stage, 2)
    action.cancel()
    position = actor.position
    tick(stage, 30)
    assert actor.position == position
    actor.move_cell(world, direction=90)
    with pytest.raises(ValueError, match="cell center"):
        tick(stage)


@pytest.mark.parametrize("physical", [False, True])
def test_live_tile_edit_stops_before_obstacle(arena: tuple[Stage, TileMap], physical: bool) -> None:
    stage, world = arena
    actor = Sprite(
        Image.rectangle(10, 10), body_type=BodyType.KINEMATIC if physical else BodyType.NONE
    )
    actor.position = world.cell_center(row=1, column=1)
    stage.add(actor)
    action = actor.move_cell(world, direction=90)
    tick(stage, 2)
    world.set_tile(row=1, column=2, tile="#")
    tick(stage, 20)
    assert action.cancelled
    assert actor.bounds.right <= 64 + 1e-6


def test_physical_actor_clearance_and_filters(arena: tuple[Stage, TileMap]) -> None:
    stage, world = arena
    tank = Sprite(Image.rectangle(10, 10), body_type=BodyType.KINEMATIC)
    tank.position = world.cell_center(row=1, column=1)
    blocker = Sprite(Image.rectangle(10, 10), x=80, y=60, body_type=BodyType.STATIC)
    stage.add(tank)
    stage.add(blocker)
    tank.move_cell(world, direction=90)
    tick(stage, 14)
    assert tank.position == (48, 60)
    blocker.body.collision_group = "friend"
    tank.body.collides_with = {"terrain"}
    tank.move_cell(world, direction=90)
    tick(stage, 14)
    assert tank.position == (80, 60)


def test_dynamic_and_competing_during_reject(arena: tuple[Stage, TileMap]) -> None:
    stage, world = arena
    actor = Sprite(Image.rectangle(10, 10))
    actor.position = world.cell_center(row=1, column=1)
    stage.add(actor)
    actor.move_cell(world, direction=90)
    with pytest.raises(PhysicsError):
        tick(stage)
    actor.remove()
    actor.body_type = BodyType.NONE
    stage.add(actor)
    actor.act(
        Script().during(
            Script().move_cell(world, direction=90),
            meanwhile=Script().move_cell(world, direction=180),
        )
    )
    with pytest.raises(StageError, match="During"):
        tick(stage)
