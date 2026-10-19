"""Grid routes are bounded immutable queries; existing actions own movement."""

from pathlib import Path

import pytest

from plocks import NavigationError, Sprite, Stage, TileMap
from plocks._runtime import advance, close

IMAGE = Path(__file__).parent / "fixtures/games/state_proof/assets/hero.png"


def grid(rows: list[str]) -> TileMap:
    """A small authored grid with two blocking kinds and non-square cells."""
    return TileMap(
        rows, {"#": IMAGE, "P": IMAGE}, tile_size=(32, 24), solid={"#"}, one_way={"P"}, x=-80, y=60
    )


def ticks(stage: Stage, count: int) -> None:
    """Run the shared simulation from its zero-time baseline."""
    if not stage.running:
        stage._state = "running"
        stage._last_wall = 0
    for _ in range(count):
        advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)


def test_route_detours_around_walls_with_exact_endpoints_and_stable_order() -> None:
    """A shortest four-neighbor path is deterministic and independent of camera."""
    world = grid([".....", ".###.", "....."])
    start = world.cell_center(row=1, column=0)
    goal = world.cell_center(row=1, column=4)
    path = world.find_path(start=start, goal=goal)
    assert path is not None and path[0] == start and path[-1] == goal
    assert len(path) == 7
    assert path == world.find_path(start=start, goal=goal)
    assert all(
        world.get_tile(row=cell[0], column=cell[1]) is None
        for point in path
        if (cell := world.cell_at(x=point[0], y=point[1])) is not None
    )
    assert world.find_path(start=start, goal=start) == (start,)
    shifted = (start[0] + 2, start[1] + 1)
    assert world.find_path(start=shifted, goal=start) == (shifted, start)


def test_budget_failure_is_distinct_from_unreachable_and_invalid_points() -> None:
    """Unknown reachability at a bounded cutoff is not misreported as no route."""
    world = grid(["..#..", "..#..", "..P.."])
    start = world.cell_center(row=0, column=0)
    goal = world.cell_center(row=0, column=4)
    assert world.find_path(start=start, goal=goal) is None
    with pytest.raises(NavigationError, match="max_nodes=1"):
        world.find_path(start=start, goal=goal, max_nodes=1)
    with pytest.raises(ValueError):
        world.find_path(start=(1000, 0), goal=goal)
    with pytest.raises(ValueError):
        world.find_path(start=start, goal=goal, max_nodes=0)
    with pytest.raises(IndexError):
        world.cell_center(row=-1, column=0)
    with pytest.raises(ValueError):
        world.find_path(start=(float("nan"), 0), goal=goal)


def test_footprint_clearance_and_map_edits_are_sampled_per_query() -> None:
    """A large actor cannot use a narrow passage; editing cells invalidates no cache."""
    world = grid([".....", "#####", "....."])
    world.set_tile(row=1, column=2, tile=None)
    start = world.cell_center(row=0, column=2)
    goal = world.cell_center(row=2, column=2)
    actor = Sprite(IMAGE)
    actor.scale = 0.1
    path = world.find_path(start=start, goal=goal, actor=actor)
    assert path is not None
    actor.scale = 100
    assert world.find_path(start=start, goal=goal, actor=actor) is None
    world.set_tile(row=1, column=2, tile="#")
    assert world.find_path(start=start, goal=goal) is None
    assert path[0] == start and path[-1] == goal


def test_diagonal_corner_cutting_is_not_a_route() -> None:
    """Diagonal empty cells cannot connect across two blocked cardinal neighbors."""
    world = grid([".#", "#."])
    assert (
        world.find_path(
            start=world.cell_center(row=0, column=0), goal=world.cell_center(row=1, column=1)
        )
        is None
    )


def test_shared_route_script_has_independent_actions_after_chains_and_cancellation() -> None:
    """Waypoints snapshot once; each action uses existing timing and conflict ownership."""
    world = Stage()
    a, b = Sprite(IMAGE), Sprite(IMAGE)
    try:
        world.add(a)
        world.add(b)
        points = [(2.0, 0.0), (2.0, 2.0)]
        script = a.sequence().follow_path(points, speed=20)
        points.append((999, 999))
        first, second = a.act(script), b.act(script)
        later = a.move_to(x=10, after=first)
        ticks(world, 20)
        assert first.done and second.done and later.done
        assert a.position == (10, 2) and b.position == (2, 2)
        moving = b.follow_path(((100, 100),), speed=20)
        ticks(world, 2)
        frozen_y = b.y
        b.x = -10
        assert moving.cancelled
        ticks(world, 5)
        assert b.position == (-10, frozen_y)
        with pytest.raises(ValueError):
            a.follow_path((), speed=20)
        with pytest.raises(ValueError):
            a.follow_path(((0, 0),), speed=0)
    finally:
        close(world)


def test_fractional_path_durations_do_not_round_at_each_segment() -> None:
    """Many short segments complete on the total exact timeline, including Puppets."""
    from plocks import Joint, Puppet, Skeleton

    stage = Stage()
    puppet = Puppet(Skeleton({"root": Joint(None)}), parts={"root": IMAGE})
    stage.add(puppet)
    try:
        action = puppet.follow_path(((i / 10, 0) for i in range(11)), speed=10)
        ticks(stage, 7)
        assert action.done and puppet.position == (1, 0)
    finally:
        close(stage)


def test_physical_dynamic_actor_keeps_authored_movement_restriction() -> None:
    """Navigation composes existing glides rather than bypassing physical ownership."""
    from plocks import PhysicsError

    stage = Stage(physics=True)
    actor = Sprite(IMAGE)
    stage.add(actor)
    actor.follow_path(((10, 0),))
    try:
        with pytest.raises(PhysicsError, match="kinematic"):
            ticks(stage, 2)
    finally:
        close(stage)


def test_endpoint_inside_blocked_cell_is_not_a_zero_length_success() -> None:
    """Cell addressing determines blocked endpoints even when a point touches an edge."""
    world = grid([".#."])
    edge = (world.x + 32, world.y - 12)
    assert world.cell_at(x=edge[0], y=edge[1]) == (0, 1)
    assert world.find_path(start=edge, goal=edge) is None
