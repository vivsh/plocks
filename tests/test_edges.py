"""Viewport and fixed-world edge observations use the simulation-owned event phase."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from plocks import (
    Action,
    Actor,
    BodyType,
    Bounds,
    Edge,
    Effect,
    Event,
    Image,
    Joint,
    Puppet,
    RotationStyle,
    Skeleton,
    Sprite,
    Stage,
    StageError,
    TileMap,
    WhenBusy,
)
from plocks._runtime import advance, close


@pytest.fixture
def stage() -> Iterator[Stage]:
    owner = Stage(width=200, height=100)
    owner._state = "running"
    owner._last_wall = 0
    yield owner
    close(owner)


def tick(stage: Stage, count: int = 1) -> None:
    for _ in range(count):
        advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)


def sprite(stage: Stage) -> Sprite:
    actor = Sprite(Image.rectangle(10, 10, color="orange"))
    stage.add(actor)
    return actor


def test_first_viewport_path_does_not_block_another_actor(stage: Stage) -> None:
    hero, friend = sprite(stage), sprite(stage)
    friend.y = -20
    events: list[frozenset[Edge]] = []

    @hero.on_edge()
    def reached(event: Event[Sprite, frozenset[Edge]]) -> None:
        assert event.source is stage and event.target is hero
        assert event.target.touching_edge()
        events.append(event.data)

    hero.glide_to(x=95, seconds=0.2)
    friend.glide_by(x=60, seconds=1)
    tick(stage, 30)
    assert events == [frozenset({Edge.RIGHT})]
    assert friend.x == pytest.approx(30)
    hero.y = 45
    tick(stage, 2)
    assert events[-1] == frozenset({Edge.RIGHT, Edge.TOP}) and len(events) == 2
    tick(stage, 35)
    assert friend.x == 60 and len(events) == 2


def test_departure_alone_does_not_notify_but_reentry_does(stage: Stage) -> None:
    hero = sprite(stage)
    hero.position = (-95, 45)
    events: list[frozenset[Edge]] = []

    @hero.on_edge()
    def reached(event: Event[Sprite, frozenset[Edge]]) -> None:
        events.append(event.data)

    tick(stage, 4)
    assert events == [frozenset({Edge.LEFT, Edge.TOP})]
    hero.y = 0
    tick(stage)
    assert len(events) == 1
    hero.y = 45
    tick(stage)
    assert events[-1] == frozenset({Edge.LEFT, Edge.TOP}) and len(events) == 2
    assert events[0] is not events[1]


def test_sampling_uses_camera_updated_in_the_same_tick(stage: Stage) -> None:
    hero = sprite(stage)
    anchor = sprite(stage)
    events: list[frozenset[Edge]] = []

    @hero.on_edge()
    def reached(event: Event[Sprite, frozenset[Edge]]) -> None:
        events.append(event.data)

    anchor.x = 95
    stage.follow(anchor)
    tick(stage)
    assert stage.camera == (95, 0)
    assert events == [frozenset({Edge.LEFT})]
    stage.follow(hero)
    tick(stage)
    assert not hero.touching_edge() and len(events) == 1


@pytest.mark.parametrize(
    "position, edges",
    [
        ((-95, 0), {Edge.LEFT}),
        ((95, 0), {Edge.RIGHT}),
        ((0, -45), {Edge.BOTTOM}),
        ((0, 45), {Edge.TOP}),
        ((-120, 200), {Edge.LEFT, Edge.TOP}),
        ((500, -500), {Edge.RIGHT, Edge.BOTTOM}),
        ((-94.999, 44.999), set()),
    ],
)
def test_sides_include_equality_and_crossings(
    stage: Stage, position: tuple[float, float], edges: set[Edge]
) -> None:
    hero = sprite(stage)
    hero.position = position
    observed: list[frozenset[Edge]] = []

    @hero.on_edge()
    def reached(event: Event[Sprite, frozenset[Edge]]) -> None:
        observed.append(event.data)

    assert hero.touching_edge() is bool(edges)
    tick(stage)
    assert observed == ([frozenset(edges)] if edges else [])


def test_explicit_bounds_detached_zero_extent_and_oversized_actor(stage: Stage) -> None:
    hero = Sprite(Image.rectangle(400, 300))
    area = Bounds(-100, -50, 100, 50)
    assert hero.touching_edge(area)
    with pytest.raises(StageError):
        hero.touching_edge()
    with pytest.raises(StageError):
        hero.on_edge(area)(lambda event: None)
    stage.add(hero)
    observed: list[frozenset[Edge]] = []

    @hero.on_edge()
    def reached(event: Event[Sprite, frozenset[Edge]]) -> None:
        observed.append(event.data)

    tick(stage)
    assert observed == [frozenset(Edge)]
    assert hero.touching_edge(Bounds(0, 0, 0, 0))
    hero.remove()
    assert hero.touching_edge(area)
    close(stage)
    assert hero.touching_edge(area)
    with pytest.raises(StageError):
        hero.touching_edge()


def test_tilemap_bounds_is_a_fixed_snapshot_not_a_live_map(stage: Stage) -> None:
    hero = sprite(stage)
    world = TileMap(["##"], {"#": hero.image}, tile_size=(10, 10), x=-15, y=5)
    stage.add(world)
    fixed = world.bounds
    seen: list[frozenset[Edge]] = []

    @hero.on_edge(fixed)
    def reached(event: Event[Sprite, frozenset[Edge]]) -> None:
        seen.append(event.data)

    tick(stage)
    assert seen == [frozenset({Edge.RIGHT, Edge.BOTTOM, Edge.TOP})]
    world.x = 500
    tick(stage)
    assert len(seen) == 1 and stage._edges[0].bounds is fixed
    assert hero.touching_edge(fixed) and hero.touching_edge(world.bounds)
    assert hero.position == (0, 0)


def test_camera_and_fixed_registration_are_distinct(stage: Stage) -> None:
    hero = sprite(stage)
    seen: list[tuple[str, frozenset[Edge]]] = []

    @hero.on_edge()
    def viewport(event: Event[Sprite, frozenset[Edge]]) -> None:
        seen.append(("viewport", event.data))

    @hero.on_edge(stage.world_bounds)
    def fixed(event: Event[Sprite, frozenset[Edge]]) -> None:
        seen.append(("fixed", event.data))

    stage.camera = (95, 0)
    tick(stage)
    assert seen == [("viewport", frozenset({Edge.LEFT}))] and len(stage._edges) == 2
    stage.camera = (0, 0)
    hero.x = 95
    tick(stage)
    assert seen[-2:] == [("viewport", frozenset({Edge.RIGHT})), ("fixed", frozenset({Edge.RIGHT}))]


def test_anchors_rotation_scale_styles_and_hidden_effects_use_visual_bounds(stage: Stage) -> None:
    hero = Sprite(Image.rectangle(20, 10).with_anchor(0, 0))
    stage.add(hero)
    hero.visible = False
    hero.set_effect(Effect.GHOST, 100)
    first = Bounds(-30, -30, 20, 30)
    assert hero.bounds == Bounds(0, -10, 20, 0) and hero.touching_edge(first)
    hero.direction = 0
    assert hero.bounds == Bounds(0, 0, 10, 20) and not hero.touching_edge(first)
    hero.scale = 2
    assert hero.touching_edge(Bounds(-100, -100, 100, 40))
    hero.rotation_style = RotationStyle.NONE
    assert hero.bounds == Bounds(0, -20, 40, 0)
    tick(stage)
    assert hero.touching_edge(Bounds(-100, -100, 40, 100))


def puppet(stage: Stage) -> Puppet:
    skeleton = Skeleton({"root": Joint(None)})
    result = Puppet(skeleton, parts={"root": Image.rectangle(20, 10).with_anchor(0, 0)})
    stage.add(result)
    return result


def test_puppet_pose_corners_and_independent_clone_history(stage: Stage) -> None:
    person = puppet(stage)
    area = Bounds(-10, -100, 100, 100)
    seen: list[Puppet] = []

    @person.on_edge(area)
    def reached(event: Event[Puppet, frozenset[Edge]]) -> None:
        assert event.data == frozenset({Edge.LEFT})
        seen.append(event.target)

    person.pose = person.pose.with_angles({"root": 90})
    tick(stage)
    assert person.touching_edge(area) and seen == [person]
    copy = person.clone()
    tick(stage)
    assert seen == [person, copy]
    assert stage._edges[0].handlers[0] is not stage._edges[1].handlers[0]
    copy.remove()
    assert len(stage._edges) == 1 and person._stage is stage
    later = person.clone()
    tick(stage)
    assert seen[-1] is later and len(seen) == 3


def test_same_bounds_group_history_but_not_listener_state(stage: Stage) -> None:
    hero = sprite(stage)
    hero.x = 95
    events: list[str] = []

    @hero.on_edge(Bounds(-100, -50, 100, 50))
    def first(event: Event[Sprite, frozenset[Edge]]) -> None:
        events.append("first")

    tick(stage)

    @hero.on_edge(Bounds(-100.0, -50.0, 100.0, 50.0))
    def second(event: Event[Sprite, frozenset[Edge]]) -> None:
        events.append("second")

    tick(stage)
    assert events == ["first"] and len(stage._edges) == 1
    hero.x = 0
    tick(stage)
    hero.x = 95
    tick(stage)
    assert events == ["first", "first", "second"]


def test_all_watch_payloads_and_handlers_are_snapshotted_before_dispatch(stage: Stage) -> None:
    first, second = sprite(stage), sprite(stage)
    first.x = second.x = 95
    events: list[str] = []

    def late(event: Event[Sprite, frozenset[Edge]]) -> None:
        events.append("late")

    @first.on_edge()
    def reached(event: Event[Sprite, frozenset[Edge]]) -> None:
        events.append("first")
        second.on_edge()(late)
        second.x = 0

    @second.on_edge()
    def other(event: Event[Sprite, frozenset[Edge]]) -> None:
        assert event.data == frozenset({Edge.RIGHT})
        events.append("second")

    tick(stage)
    assert events == ["first", "second"]
    tick(stage)
    second.x = 95
    tick(stage)
    assert events == ["first", "second", "second", "late"]


@pytest.mark.parametrize("readd", [False, True])
def test_removal_in_callback_invalidates_remaining_payload(stage: Stage, readd: bool) -> None:
    hero = sprite(stage)
    hero.x = 95
    events: list[str] = []

    @hero.on_edge()
    def first(event: Event[Sprite, frozenset[Edge]]) -> None:
        events.append("first")
        event.target.remove()
        if readd:
            stage.add(event.target)

    @hero.on_edge()
    def late(event: Event[Sprite, frozenset[Edge]]) -> None:
        events.append("late")

    tick(stage)
    assert events == ["first"]
    if not readd:
        stage.add(hero)
    tick(stage)
    assert events == ["first", "first"]


@pytest.mark.parametrize("reason", ["user", "focus", "alert"])
def test_pause_reasons_freeze_sampling_and_history(stage: Stage, reason: str) -> None:
    hero = sprite(stage)
    events: list[frozenset[Edge]] = []

    @hero.on_edge()
    def reached(event: Event[Sprite, frozenset[Edge]]) -> None:
        events.append(event.data)

    stage._set_pause(reason, True)
    hero.x = 95
    tick(stage, 5)
    assert not events and stage._edges[0].previous == frozenset()
    assert hero.touching_edge()
    stage._set_pause(reason, False)
    tick(stage, 2)
    assert events == [frozenset({Edge.RIGHT})]


def test_pause_in_handler_discards_rest_of_batch_without_replay(stage: Stage) -> None:
    hero, other = sprite(stage), sprite(stage)
    hero.x = other.x = 95
    events: list[str] = []

    @hero.on_edge()
    def first(event: Event[Sprite, frozenset[Edge]]) -> None:
        events.append("first")
        stage.pause()

    @hero.on_edge()
    def skipped(event: Event[Sprite, frozenset[Edge]]) -> None:
        events.append("skipped")

    @other.on_edge()
    def last(event: Event[Sprite, frozenset[Edge]]) -> None:
        events.append("last")

    tick(stage)
    stage.resume()
    tick(stage)
    assert events == ["first"]
    other.y = 45
    tick(stage)
    assert events == ["first", "last"]


@pytest.mark.parametrize("restart", [False, True])
def test_busy_policy_for_new_edges_uses_existing_action_roots(stage: Stage, restart: bool) -> None:
    hero = sprite(stage)
    hero.x = 95
    hero.on_edge(
        script=hero.sequence().wait(1), when_busy=WhenBusy.RESTART if restart else WhenBusy.IGNORE
    )
    tick(stage)
    first = stage._actions[0]
    hero.y = 45
    tick(stage)
    assert first.cancelled is restart
    assert len(stage._actions) == 1
    tick(stage, 70)
    assert not stage._actions


def test_direct_script_fixed_bounds_and_returned_action(stage: Stage) -> None:
    hero = sprite(stage)
    hero.on_edge(Bounds(-10, -10, 10, 10), hero.sequence().set_effect(Effect.COLOR, 50))
    hero.x = 5
    tick(stage, 2)
    assert hero._effects[Effect.COLOR] == 50

    @hero.on_edge()
    def reached(event: Event[Sprite, frozenset[Edge]]) -> Action:
        return event.target.say("Edge!", seconds=0.1)

    hero.x = 95
    tick(stage, 2)
    assert hero._bubble is not None
    tick(stage, 10)
    assert hero._bubble is None


def test_physical_contact_is_not_created_by_an_arbitrary_rectangle() -> None:
    owner = Stage(width=200, height=100, physics=True)
    owner.physics.gravity = (0, 0)
    hero = Sprite(Image.rectangle(10, 10), x=95, body_type=BodyType.KINEMATIC)
    owner.add(hero)
    owner._state = "running"
    owner._last_wall = 0
    hits: list[object] = []
    from plocks import Collision

    @hero.on_hit
    def hit(event: Event[Sprite, Collision]) -> None:
        hits.append(event.data)

    before = hero.body.shape
    hero.body.velocity = (10, 0)
    try:
        tick(owner)
        assert hero.touching_edge() and not hits
        assert hero.body.velocity == (10, 0) and hero.body.shape == before
    finally:
        close(owner)


def test_validation_and_exact_approved_inventory(stage: Stage) -> None:
    from collections.abc import Callable
    from dataclasses import fields
    from typing import cast

    import plocks
    from plocks import Body, Physics
    from plocks._edges import _EdgeWatch

    hero = sprite(stage)
    bad = cast(Bounds, "viewport")
    with pytest.raises(TypeError, match="Bounds"):
        hero.touching_edge(bad)
    with pytest.raises(TypeError, match="Bounds"):
        hero.on_edge(bad)
    with pytest.raises(TypeError, match="WhenBusy"):
        hero.on_edge(when_busy=cast(WhenBusy, "ignore"))(lambda event: None)

    async def async_callback(event: Event[Sprite, frozenset[Edge]]) -> None:
        pass

    with pytest.raises(TypeError, match="synchronous"):
        hero.on_edge()(cast(Callable[[Event[Sprite, frozenset[Edge]]], None], async_callback))
    assert not stage._edges
    assert "Edge" in plocks.__all__ and len(Edge) == 4
    assert tuple(field.name for field in fields(_EdgeWatch)) == (
        "actor",
        "bounds",
        "handlers",
        "previous",
    )
    assert _EdgeWatch.__slots__ == ("actor", "bounds", "handlers", "previous")
    assert "_edges" in Stage.__slots__
    assert all("_edges" not in cls.__slots__ for cls in (Sprite, Puppet, Body, Physics))


def test_quotas_and_failed_clone_inheritance_leave_source_intact(stage: Stage) -> None:
    hero = sprite(stage)

    def reached(event: Event[Sprite, frozenset[Edge]]) -> None:
        pass

    for _ in range(512):
        hero.on_edge()(reached)
    copy = hero.clone()
    assert len(stage._edges) == 2
    with pytest.raises(StageError, match="1024 edge handlers"):
        hero.clone()
    assert stage.clone_count == 1 and hero._stage is stage and copy._stage is stage
    assert sum(len(w.handlers) for w in stage._edges) == 1024
    with pytest.raises(StageError, match="1024 edge handlers"):
        hero.on_edge()(reached)


def test_partial_clone_rollback_prunes_edge_watches(
    stage: Stage, monkeypatch: pytest.MonkeyPatch
) -> None:
    from plocks import _cloning

    hero = sprite(stage)

    @hero.on_edge()
    def reached(event: Event[Sprite, frozenset[Edge]]) -> None:
        pass

    inherit = _cloning._inherit

    def failure(owner: Stage, source: Actor, target: Actor) -> None:
        inherit(owner, source, target)
        assert len(owner._edges) == 2
        raise LookupError("rollback after edge inheritance")

    monkeypatch.setattr(_cloning, "_inherit", failure)
    with pytest.raises(LookupError, match="rollback after edge inheritance"):
        hero.clone()
    assert len(stage._edges) == 1 and stage._edges[0].actor is hero and stage.clone_count == 0


def test_callback_failure_preserves_exception_and_cleans_resources() -> None:
    owner = Stage(width=200, height=100)
    hero = Sprite(Image.rectangle(10, 10), x=95)
    owner.add(hero)

    @hero.on_edge()
    def reached(event: Event[Sprite, frozenset[Edge]]) -> None:
        raise LookupError("edge callback failed")

    with pytest.raises(LookupError, match="edge callback failed"):
        owner.run()
    assert (
        owner._state == "closed" and not owner._edges and not owner._actions and hero._stage is None
    )


def test_an_earlier_touch_callback_pause_skips_the_edge_phase(stage: Stage) -> None:
    hero, coin = sprite(stage), sprite(stage)
    hero.x = coin.x = 95
    observed: list[frozenset[Edge]] = []

    @hero.on_touch(coin)
    def overlap(event: Event[Sprite, Sprite]) -> None:
        stage.pause()

    @hero.on_edge()
    def reached(event: Event[Sprite, frozenset[Edge]]) -> None:
        observed.append(event.data)

    tick(stage)
    assert stage.paused and not observed and not stage._edges[0].previous
    stage.resume()
    tick(stage, 2)
    assert observed == [frozenset({Edge.RIGHT})]


def test_closing_in_a_handler_skips_later_deliveries(stage: Stage) -> None:
    hero = sprite(stage)
    hero.x = 95
    observed: list[str] = []

    @hero.on_edge()
    def stop(event: Event[Sprite, frozenset[Edge]]) -> None:
        observed.append("stop")
        stage.stop()

    @hero.on_edge()
    def later(event: Event[Sprite, frozenset[Edge]]) -> None:
        observed.append("later")

    tick(stage)
    assert observed == ["stop"] and not stage.running
    close(stage)
    assert not stage._edges


def test_inherited_edge_handler_can_remove_its_clone_repeatedly(stage: Stage) -> None:
    source = sprite(stage)
    source.x = 95
    removed: list[Sprite] = []

    @source.on_edge()
    def reached(event: Event[Sprite, frozenset[Edge]]) -> None:
        if event.target.is_clone:
            removed.append(event.target)
            event.target.remove()

    tick(stage)
    for _ in range(3):
        copy = source.clone()
        tick(stage)
        assert removed[-1] is copy and copy._stage is None
        assert source._stage is stage and len(stage._edges) == 1
    assert len(removed) == 3 and source.clone_count == 0


def test_complete_downloadable_edge_activity(tmp_path: Path) -> None:
    import runpy
    import shutil
    from typing import cast

    from plocks import GamepadButton, GamepadInput, GamepadPress, Label

    root = Path(__file__).parents[1]
    shutil.copy2(root / "docs/activities/edges.py", tmp_path / "edges.py")
    shutil.copytree(root / "src/plocks/_games/dino_run/assets", tmp_path / "assets")
    values = runpy.run_path(str(tmp_path / "edges.py"))
    owner = cast(Stage, values["stage"])
    hero = cast(Sprite, values["hero"])
    level_text, view_text = cast(Label, values["level_text"]), cast(Label, values["view_text"])

    @owner.on_bot(gamepad=owner.gamepads[0])
    def drive(event: Event[Stage, float]) -> GamepadInput:
        return GamepadInput(left_stick=(1, 0))

    owner._state = "running"
    owner._last_wall = 0
    try:
        tick(owner, 100)
        assert "right" in level_text.text and "right" in view_text.text
        assert hero.touching_edge()
        owner._pending.append(GamepadPress(owner.gamepads[0], GamepadButton.A))
        tick(owner)
        assert not hero.touching_edge() and hero.x == pytest.approx(2.5)
        assert "not reached" in level_text.text and "not reached" in view_text.text
    finally:
        close(owner)


def test_rejected_duplicate_add_preserves_history_and_clone_listeners(stage: Stage) -> None:
    hero = sprite(stage)
    hero.x = 95
    observed: list[Sprite] = []

    @hero.on_edge()
    def reached(event: Event[Sprite, frozenset[Edge]]) -> None:
        observed.append(event.target)

    tick(stage)
    original = stage._edges[0].previous
    with pytest.raises(ValueError, match="already"):
        stage.add(hero)
    assert stage._edges[0].previous is original
    tick(stage)
    assert observed == [hero]
    copy = hero.clone()
    tick(stage)
    previous = stage._edges[1].previous
    with pytest.raises(ValueError, match="already"):
        stage.add(copy)
    assert len(stage._edges) == 2 and stage._edges[1].previous is previous
    tick(stage)
    assert observed == [hero, copy]
    copy.x = 0
    tick(stage)
    copy.x = 95
    tick(stage)
    assert observed == [hero, copy, copy]
