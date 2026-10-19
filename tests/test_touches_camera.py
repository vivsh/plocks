"""Overlap history, native sensors and simulation-owned camera following."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from plocks import (
    BodyType,
    Bounds,
    Box,
    Event,
    Joint,
    PhysicsError,
    Puppet,
    Skeleton,
    Sprite,
    Stage,
)
from plocks._runtime import advance, close

IMAGE = Path(__file__).parent / "fixtures/games/state_proof/assets/hero.png"


@pytest.fixture
def stage() -> Iterator[Stage]:
    """Own ordinary test actors and their transition history."""
    world = Stage(width=200, height=100)
    world._state = "running"
    world._last_wall = 0
    yield world
    close(world)


def ticks(stage: Stage, count: int = 1) -> None:
    """Use the shared simulation order rather than invoke listeners directly."""
    for _ in range(count):
        advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)


@pytest.mark.parametrize("puppet", [False, True])
def test_enter_leave_share_history_and_hidden_actors_still_touch(
    stage: Stage, puppet: bool
) -> None:
    """Each ordered pair stores one transition even with both listener kinds."""
    actor = (
        Puppet(Skeleton({"root": Joint(None)}), parts={"root": IMAGE}) if puppet else Sprite(IMAGE)
    )
    coin = Sprite(IMAGE)
    stage.add(actor)
    stage.add(coin)
    log: list[str] = []
    actor.visible = False
    actor.on_touch(coin)(lambda event: log.append("enter"))
    actor.on_touch_end(coin)(lambda event: log.append("leave"))
    ticks(stage, 3)
    assert log == ["enter"] and len(stage._touches) == 1
    actor.x = 100
    ticks(stage, 3)
    assert log == ["enter", "leave"]
    actor.x = 0
    ticks(stage)
    assert log == ["enter", "leave", "enter"]


def test_removal_suppresses_later_callbacks_and_readding_resets_history(stage: Stage) -> None:
    """A collected object cannot notify later listeners from the old transition batch."""
    hero, coin = Sprite(IMAGE), Sprite(IMAGE)
    stage.add(hero)
    stage.add(coin)
    log: list[str] = []

    @hero.on_touch(coin)
    def collect(event: Event[Sprite, Sprite]) -> None:
        log.append("collect")
        stage.remove(event.data)

    hero.on_touch(coin)(lambda event: log.append("late"))
    hero.on_touch_end(coin)(lambda event: log.append("leave"))
    ticks(stage)
    assert log == ["collect"]
    stage.add(coin)
    ticks(stage)
    assert log == ["collect", "collect"]


def test_registration_snapshot_pause_and_clone_history(stage: Stage) -> None:
    """Clones inherit fresh subscriptions, and paused time never samples overlap."""
    hero, coin = Sprite(IMAGE), Sprite(IMAGE)
    stage.add(hero)
    stage.add(coin)
    receivers: list[Sprite] = []

    @hero.on_touch(coin)
    def entered(event: Event[Sprite, Sprite]) -> None:
        receivers.append(event.target)

    ticks(stage)
    stage.pause()
    copy = hero.clone()
    ticks(stage, 3)
    assert receivers == [hero]
    stage.resume()
    ticks(stage, 2)
    assert receivers == [hero, copy]
    stage.remove(copy)
    assert all(w.actor is not copy and w.other is not copy for w in stage._touches)


def test_sensors_preserve_native_settings_and_do_not_support_grounding() -> None:
    """A sensor survives shape/scale changes and cloning without becoming a platform."""
    world = Stage(physics=True)
    world._state = "running"
    world._last_wall = 0
    floor = Sprite(IMAGE, body_type=BodyType.STATIC)
    rider = Sprite(IMAGE, y=15)
    try:
        world.add(floor)
        world.add(rider)
        floor.body.shape = Box(200, 10)
        rider.body.shape = Box(10, 10)
        floor.body.sensor = True
        floor.scale = 2
        copy = floor.clone()
        copy.x = 300
        assert copy.body.sensor and floor.body.sensor
        ticks(world, 30)
        assert rider.y < -30 and not rider.body.grounded and not floor.body.grounded
        with pytest.raises(TypeError):
            setattr(floor.body, "sensor", 1)  # noqa: B010 -- exercise validation of an untyped caller
        world.remove(copy)
        world.add(copy)
        assert not copy.body.sensor
        one_way = Sprite(IMAGE, body_type=BodyType.STATIC, one_way=True)
        world.add(one_way)
        with pytest.raises(PhysicsError, match="one-way"):
            one_way.body.sensor = True
        assert not one_way.body.sensor
    finally:
        close(world)


def test_follow_clamps_smooths_and_manual_assignment_validates_before_cancelling(
    stage: Stage,
) -> None:
    """Camera progress is just its position; bounds and interruption have no mirror state."""
    hero = Sprite(IMAGE, x=490, y=290)
    stage.add(hero)
    stage.follow(hero, bounds=Bounds(-500, -300, 500, 300))
    ticks(stage)
    assert stage.camera == (400, 250)
    stage.follow(hero, bounds=Bounds(-20, -10, 20, 10))
    ticks(stage)
    assert stage.camera == (0, 0)
    stage.follow(hero, smoothing=1)
    ticks(stage)
    assert 0 < stage.camera[0] < hero.x
    with pytest.raises(ValueError):
        stage.camera = (float("nan"), 0)
    assert stage._camera_follow is not None
    stage.camera = (12, 30)
    ticks(stage)
    assert stage.camera == (12, 30) and stage._camera_follow is None


def test_follow_pause_and_removal_freeze_camera(stage: Stage) -> None:
    """Paused simulation or removal cannot advance a retained following target."""
    hero = Sprite(IMAGE, x=20)
    stage.add(hero)
    stage.follow(hero)
    ticks(stage)
    stage.pause()
    hero.x = 100
    ticks(stage, 4)
    assert stage.camera == (20, 0)
    stage.resume()
    ticks(stage, 2)
    assert stage.camera == (100, 0)
    stage.remove(hero)
    assert stage._camera_follow is None


@pytest.mark.parametrize("restart", [False, True])
def test_touch_busy_policy_and_registration_snapshot(stage: Stage, restart: bool) -> None:
    """Accepted transitions reuse normal action busy rules and snapshot listeners."""
    from plocks import Script, WhenBusy

    hero, coin = Sprite(IMAGE), Sprite(IMAGE)
    stage.add(hero)
    stage.add(coin)
    seen: list[str] = []
    busy = WhenBusy.RESTART if restart else WhenBusy.IGNORE
    hero.on_touch(coin, Script().wait(1), when_busy=busy)

    @hero.on_touch(coin)
    def register(event: Event[Sprite, Sprite]) -> None:
        seen.append("first")
        hero.on_touch(coin)(lambda event: seen.append("late"))

    ticks(stage)
    first = stage._actions[0]
    assert seen == ["first"]
    hero.x = 100
    ticks(stage)
    hero.x = 0
    ticks(stage)
    assert first.cancelled is restart
    assert seen == ["first", "first", "late"]
    assert len(stage._actions) == 1


def test_clone_touch_budget_failure_rolls_back_membership_and_handlers(stage: Stage) -> None:
    """A clone that cannot inherit its watched pairs leaves no partial actor or input."""
    from plocks import StageError

    hero = Sprite(IMAGE)
    stage.add(hero)
    for _ in range(1024):
        other = Sprite(IMAGE)
        stage.add(other)
        hero.on_touch(other)(lambda event: None)
    before = stage.objects
    with pytest.raises(StageError, match="1024"):
        hero.clone()
    assert stage.objects == before and len(stage._touches) == 1024
    assert all(not w.actor.is_clone for w in stage._touches)


def test_tile_touch_and_callback_failure_preserve_exception_and_close() -> None:
    """Tile payloads remain typed; callback errors retire every new owner."""
    from plocks import TileMap

    world = Stage()
    hero = Sprite(IMAGE)
    tiles = TileMap(["#"], {"#": IMAGE}, tile_size=(32, 32), solid={"#"}, x=-16, y=16)
    world.add(hero)
    world.add(tiles)
    world.follow(hero)
    failure = RuntimeError("touch failed")

    @hero.on_touch(tiles)
    def fail(event: Event[Sprite, TileMap]) -> None:
        assert event.data is tiles
        raise failure

    with pytest.raises(RuntimeError) as captured:
        world.run()
    assert captured.value is failure
    assert not world._touches and world._camera_follow is None and not world.objects


def test_smoothed_follow_clamps_current_view_when_bounds_change(stage: Stage) -> None:
    """A newly bounded follow cannot ease through space outside the allowed viewport."""
    hero = Sprite(IMAGE, x=100)
    stage.add(hero)
    stage.camera = (5000, 5000)
    stage.follow(hero, bounds=Bounds(-400, -200, 400, 200), smoothing=1)
    ticks(stage)
    assert stage.world_bounds.right <= 400 and stage.world_bounds.top <= 200
    stage.follow(hero, bounds=Bounds(20, 30, 40, 50), smoothing=1)
    ticks(stage)
    assert stage.camera == (30, 40)
