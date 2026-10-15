"""Actor-local callbacks retain Stage ownership, deterministic targeting and cleanup."""

import asyncio
from collections.abc import Callable, Iterator
from typing import cast

import pytest
from PIL import Image

from plocks import (
    Actor,
    GlideBy,
    Joint,
    MouseButton,
    Move,
    Point,
    Puppet,
    Skeleton,
    Sprite,
    Stage,
    StageError,
    WhenBusy,
)
from plocks._runtime import advance, close, dispatch, drive


@pytest.fixture(params=["sprite", "puppet"])
def actor(request: pytest.FixtureRequest) -> Actor:
    """Use equal image bounds on both actor kinds, including transparent pixels."""
    image = Image.new("RGBA", (20, 20))
    if request.param == "sprite":
        return Sprite(image)
    return Puppet(Skeleton({"root": Joint(parent=None)}), parts={"root": image})


@pytest.fixture
def stage() -> Iterator[Stage]:
    """Keep callbacks and coroutine invocations within the test lifetime."""
    value = Stage()
    value._state = "running"
    yield value
    close(value)


def ticks(stage: Stage, count: int) -> None:
    """Drive real fixed-step orchestration with a synthetic wall clock."""
    if stage._last_wall is None:
        advance(stage, 0)
    for _ in range(count):
        assert stage._last_wall is not None
        advance(stage, stage._last_wall + 1 / stage.tick_rate)


def click(stage: Stage, position: Point = (0, 0), button: MouseButton = MouseButton.LEFT) -> None:
    """Dispatch one native-style stage-coordinate pointer event."""
    stage._pending.append((position, button))
    dispatch(stage)


def test_update_order_snapshots_and_hidden_actors[A: (Sprite, Puppet)](
    actor: A, stage: Stage
) -> None:
    """Actor/global updates share registration order and defer newly registered work."""
    stage.add(actor)
    actor.visible = False
    events: list[str] = []
    added = False

    @stage.on_update
    def first(dt: float) -> None:
        events.append("global")

    def late(dt: float) -> None:
        events.append("late")

    @actor.on_update
    def move(dt: float) -> None:
        nonlocal added
        events.append("actor")
        assert dt == 1 / stage.tick_rate
        actor.x += 60 * dt
        if not added:
            actor.on_update(late)
            added = True

    @stage.on_update
    def last(dt: float) -> None:
        events.append("last")

    assert stage._updates[1] == (actor, move)
    ticks(stage, 1)
    assert events == ["global", "actor", "last"] and actor.x == 1
    actor.stop()
    ticks(stage, 1)
    assert events[3:] == ["global", "actor", "last", "late"] and actor.x == 2


def test_update_detach_readd_and_migration[A: (Sprite, Puppet)](actor: A, stage: Stage) -> None:
    """Actor updates stay registered in their stage and never transfer implicitly."""
    stage.add(actor)

    @actor.on_update
    def move(dt: float) -> None:
        actor.x += 60 * dt

    ticks(stage, 1)
    stage.remove(actor)
    ticks(stage, 2)
    assert actor.x == 1
    other = Stage()
    try:
        other.add(actor)
        other._state = "running"
        ticks(stage, 1)
        ticks(other, 1)
        assert actor.x == 1
        other.remove(actor)
        stage.add(actor)
        ticks(stage, 1)
        assert actor.x == 2
    finally:
        close(other)


def test_registration_requires_attachment_and_sync_update[A: (Sprite, Puppet)](
    actor: A, stage: Stage
) -> None:
    """Detached registration fails and untyped async updates cannot leak coroutines."""

    def update(dt: float) -> None:
        pass

    def clicked(position: Point, button: MouseButton) -> None:
        pass

    with pytest.raises(StageError):
        actor.on_update(update)
    with pytest.raises(StageError):
        actor.on_click(clicked)
    with pytest.raises(StageError):
        actor.on_click(Move(1))
    stage.add(actor)

    async def async_update(dt: float) -> None:
        pass

    with pytest.raises(TypeError, match="synchronous"):
        actor.on_update(cast(Callable[[float], None], async_update))
    assert not stage._updates
    close(stage)
    with pytest.raises(StageError):
        actor.on_update(update)


def test_click_coordinates_camera_transforms_and_edges[A: (Sprite, Puppet)](
    actor: A, stage: Stage
) -> None:
    """Hit tests use transformed world bounds but callbacks receive stage coordinates."""
    stage.add(actor)
    actor.position = (70, -25)
    actor.scale = 2
    actor.direction = 45
    stage.camera = (30, 15)
    received: list[tuple[Point, MouseButton]] = []

    @actor.on_click
    def clicked(position: Point, button: MouseButton) -> None:
        received.append((position, button))

    bounds = actor.bounds

    def screen(point: Point) -> Point:
        return point[0] - stage.camera[0], point[1] - stage.camera[1]

    center = screen(bounds.center)
    click(stage, center, MouseButton.RIGHT)
    assert received == [(center, MouseButton.RIGHT)]
    click(stage, screen((bounds.left, bounds.top)))
    assert len(received) == 2
    click(stage, screen((bounds.right, bounds.top)))
    click(stage, screen((bounds.left, bounds.bottom)))
    assert len(received) == 2


def test_topmost_visible_actor_occludes_even_without_handlers[A: (Sprite, Puppet)](
    actor: A, stage: Stage
) -> None:
    """Layer and later insertion select the target; transparent padding still counts."""
    stage.add(actor)
    received: list[str] = []

    @actor.on_click
    def clicked(position: Point, button: MouseButton) -> None:
        received.append("actor")

    cover = Sprite(Image.new("RGBA", (20, 20)))
    stage.add(cover)
    click(stage)
    assert received == []
    cover.visible = False
    click(stage)
    assert received == ["actor"]
    cover.visible = True
    actor.layer = 2
    click(stage)
    assert received == ["actor", "actor"]


def test_click_target_snapshot_and_global_observers[A: (Sprite, Puppet)](
    actor: A, stage: Stage
) -> None:
    """A global observer removing the target does not retarget the same click below it."""
    lower = Sprite(Image.new("RGBA", (20, 20)))
    stage.add(lower)
    stage.add(actor)
    events: list[str] = []

    @lower.on_click
    def below(position: Point, button: MouseButton) -> None:
        events.append("lower")

    @actor.on_click
    def selected(position: Point, button: MouseButton) -> None:
        events.append("selected")

    @stage.on_click
    def observe(position: Point, button: MouseButton) -> None:
        events.append("global")
        if actor._stage is stage:
            stage.remove(actor)

    click(stage)
    assert events == ["global"]
    click(stage)
    assert events == ["global", "global", "lower"]
    stage.add(actor)
    click(stage)
    assert events[-1] == "global"


def test_new_click_handlers_wait_for_next_event[A: (Sprite, Puppet)](
    actor: A, stage: Stage
) -> None:
    """Global observers cannot add a new targeted callback to the current snapshot."""
    stage.add(actor)
    events: list[str] = []
    added = False

    def late(position: Point, button: MouseButton) -> None:
        events.append("late")

    @stage.on_click
    def observe(position: Point, button: MouseButton) -> None:
        nonlocal added
        if not added:
            actor.on_click(late)
            added = True

    @actor.on_click
    def selected(position: Point, button: MouseButton) -> None:
        events.append("first")

    click(stage)
    assert events == ["first"]
    click(stage)
    assert events == ["first", "first", "late"]


@pytest.mark.parametrize("busy", [WhenBusy.IGNORE, WhenBusy.RESTART])
def test_click_block_busy_and_removal[A: (Sprite, Puppet)](
    actor: A, stage: Stage, busy: WhenBusy
) -> None:
    """Repeated actor clicks share existing busy policies and removal cancels the root."""
    stage.add(actor)
    actor.on_click(GlideBy(y=60, seconds=1), when_busy=busy)
    click(stage)
    ticks(stage, 13)
    original = stage._runs[0]
    frozen = actor.y
    click(stage, (actor.x, actor.y))
    assert (stage._runs[0] is original) == (busy is WhenBusy.IGNORE)
    stage.remove(actor)
    ticks(stage, 1)
    assert actor.y == frozen and not stage._runs
    stage.add(actor)
    click(stage, (actor.x, actor.y))
    assert len(stage._runs) == 1


def test_paused_sync_clicks_and_async_invocation_ownership[A: (Sprite, Puppet)](
    actor: A, stage: Stage
) -> None:
    """Sync actor clicks work while paused; async clicks wait and are canceled on removal."""
    stage.add(actor)
    events: list[str] = []

    @actor.on_update
    def update(dt: float) -> None:
        events.append("update")

    @actor.on_click
    async def scripted(position: Point, button: MouseButton) -> None:
        events.append("start")
        await stage.wait(0.05)
        events.append("end")

    @actor.on_click
    def clicked(position: Point, button: MouseButton) -> None:
        events.append("sync")

    stage.pause()
    click(stage)
    ticks(stage, 8)
    assert events == ["sync"] and len(stage._runs) == 1
    stage.resume()
    ticks(stage, 8)
    assert "start" in events and "end" in events and "update" in events
    assert not stage._runs
    click(stage)
    assert stage._runs[0].actor is actor
    stage.remove(actor)
    assert not stage._runs


def test_legacy_stage_binding_stays_global[A: (Sprite, Puppet)](actor: A, stage: Stage) -> None:
    """The older Stage.on_click(actor, block) form still reacts anywhere on stage."""
    stage.add(actor)
    stage.on_click(actor, Move(2))
    actor.on_click(Move(3))
    click(stage, (100, 100))
    ticks(stage, 1)
    assert actor.x == 2
    click(stage, (actor.x, actor.y))
    ticks(stage, 1)
    assert actor.x == 7


@pytest.mark.parametrize("kind", ["click", "update"])
def test_callback_failures_preserve_exception_and_cleanup[A: (Sprite, Puppet)](
    actor: A, stage: Stage, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """Both new callback paths preserve the original failure and retire stage resources."""
    stage.add(actor)
    failure = ValueError("original actor failure")

    def update(dt: float) -> None:
        raise failure

    def clicked(position: Point, button: MouseButton) -> None:
        raise failure

    if kind == "update":
        actor.on_update(update)
    else:
        actor.on_click(clicked)
        stage._pending.append(((0, 0), MouseButton.LEFT))
    monkeypatch.setattr("plocks._runtime.poll", lambda value: None)
    stage._last_wall = 0
    with pytest.raises(ValueError) as caught:
        asyncio.run(drive(stage))
    assert caught.value is failure
    assert not stage._updates and not stage._clicks and not stage._runs
    assert actor._stage is None
