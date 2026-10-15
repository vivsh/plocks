"""Simulation-driven recipes, structured concurrency, and cancellation invariants."""

import asyncio
from collections.abc import Iterator
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pygame
import pytest
from PIL import Image

from plocks import (
    Block,
    BroadcastAndWait,
    Costumes,
    During,
    GlideBy,
    GlideTo,
    Key,
    Loop,
    Message,
    Move,
    PlaySound,
    Repeat,
    Script,
    Sequence,
    Signal,
    Sound,
    Sprite,
    Stage,
    StageError,
    Wait,
    WhenBusy,
)
from plocks._runtime import close, dispatch, drive
from plocks._scripts import _deliver, _sample, _step


@pytest.fixture
def stage() -> Iterator[Stage]:
    """Use exact ticks rather than wall time; always close admitted coroutines."""
    value = Stage()
    value._state = "running"
    yield value
    close(value)


def actor(stage: Stage) -> Sprite:
    """Attach an image actor for a behavior test."""
    result = Sprite(Image.new("RGBA", (4, 4), "red"))
    stage.add(result)
    return result


def ticks(stage: Stage, count: int) -> None:
    """Mirror the engine's deterministic per-tick order."""
    for _ in range(count):
        if stage.paused:
            continue
        stage._tick += 1
        _sample(stage)
        _deliver(stage)
        dispatch(stage)
        _step(stage)


def test_deferred_reuse_and_precise_sequence(stage: Stage) -> None:
    """Definitions have no progress; sequential 7-Hz durations carry fractional time."""
    first, second = actor(stage), actor(stage)
    recipe = Repeat(7, GlideBy(x=1, seconds=1 / 7))
    first.act(recipe)
    assert first.x == 0
    _step(stage)
    ticks(stage, 10)
    second.act(recipe)
    _step(stage)
    ticks(stage, 50)
    assert first.x == 7 and second.x < 7
    assert [f.name for f in fields(recipe)] == ["times", "block"]
    with pytest.raises(FrozenInstanceError):
        setattr(recipe, "times", 9)  # noqa: B010 -- exercise frozen storage without a static assignment error
    ticks(stage, 10)
    assert second.x == 7 and not stage._runs
    first.act(recipe)
    _step(stage)
    ticks(stage, 60)
    assert first.x == 14


def test_independent_axes_and_direct_interruption(stage: Stage) -> None:
    """A y jump can overlap x motion; a direct x write cancels only the x root."""
    hero = actor(stage)
    hero.act(Sequence(GlideBy(x=60, seconds=1), Move(500)))
    hero.act(GlideBy(y=60, seconds=1))
    _step(stage)
    ticks(stage, 15)
    assert hero.position == pytest.approx((15, 15))
    with pytest.raises(ValueError):
        hero.x = float("nan")
    assert len(stage._runs) == 2
    hero.x = 10
    ticks(stage, 45)
    assert hero.position == (10, 60) and not stage._runs


def test_busy_ignore_restart_and_stop(stage: Stage) -> None:
    """One registration has one invocation; restart captures its current position."""
    hero = actor(stage)
    recipe = GlideBy(y=60, seconds=1)
    stage.on_key_down(Key.SPACE, hero, recipe)
    stage._pending.append(Key.SPACE)
    dispatch(stage)
    _step(stage)
    ticks(stage, 15)
    stage._pending.append(Key.SPACE)
    dispatch(stage)
    assert len(stage._runs) == 1
    stage.on_key_down(Key.A, hero, recipe, when_busy=WhenBusy.RESTART)
    stage._pending.append(Key.A)
    dispatch(stage)
    _step(stage)
    ticks(stage, 15)
    hero.stop(recipe)
    assert not stage._runs
    frozen = hero.y
    ticks(stage, 60)
    assert hero.y == frozen


def test_during_visual_completion_and_conflict(stage: Stage) -> None:
    """Background visuals freeze when foreground finishes; overlapping branch writers fail."""
    hero = actor(stage)
    frames = (hero.costume, Sprite(Image.new("RGBA", (4, 4), "blue")).costume)
    hero.act(During(GlideTo(x=60, seconds=1), meanwhile=Loop(Costumes(frames, fps=7))))
    _step(stage)
    ticks(stage, 30)
    assert hero.x == 30
    ticks(stage, 30)
    assert not stage._runs and hero.x == 60
    frozen = hero.costume
    ticks(stage, 30)
    assert hero.costume is frozen
    hero.act(During(GlideBy(x=1, seconds=1), meanwhile=GlideBy(x=2, seconds=1)))
    with pytest.raises(StageError, match="same property"):
        _step(stage)


def test_immediate_loop_yields_and_zero_glide(stage: Stage) -> None:
    """Immediate-only loops run once per tick; zero glides still yield."""
    hero = actor(stage)
    hero.act(Loop(Move(1)))
    _step(stage)
    assert hero.x == 1
    ticks(stage, 5)
    assert hero.x == 6
    hero.stop()
    hero.act(Sequence(GlideTo(x=100, seconds=0), Move(1)))
    _step(stage)
    assert hero.x == 100
    ticks(stage, 1)
    assert hero.x == 101


def test_costume_boundary_and_detach(stage: Stage) -> None:
    """Last frames have duration; removal cancels and re-addition does not resume."""
    hero = actor(stage)
    frames = (hero.costume, Sprite(Image.new("RGBA", (4, 4), "blue")).costume)
    recipe = Costumes(frames, fps=10)
    hero.act(recipe)
    _step(stage)
    ticks(stage, 6)
    assert hero.costume is frames[1] and len(stage._runs) == 1
    stage.remove(hero)
    assert hero._stage is None and hero.costume is frames[1] and not stage._runs
    stage.add(hero)
    ticks(stage, 30)
    assert hero.costume is frames[1]
    hero.act(recipe)
    _step(stage)
    hero.costume = frames[1]
    assert not stage._runs


def test_message_factory_busy_and_join(stage: Stage) -> None:
    """Typed factories are deferred and skipped busy deliveries never evaluate them."""
    sender, receiver = actor(stage), actor(stage)
    channel = Message[int]("push")
    calls: list[int] = []

    def factory(amount: int) -> Block[Sprite]:
        calls.append(amount)
        return GlideBy(x=amount, seconds=0.2)

    stage.on_message(channel, receiver, factory)
    sender.act(Sequence(BroadcastAndWait(channel, 12), Move(5)))
    _step(stage)
    assert calls == [] and sender.x == 0
    ticks(stage, 1)
    assert calls == [12]
    stage.broadcast(channel, 99)
    ticks(stage, 1)
    assert calls == [12]
    ticks(stage, 14)
    assert receiver.x == 12 and sender.x == 5 and not stage._runs


def test_fifo_identity_and_deferred_recursive_messages(stage: Stage) -> None:
    """Same names are distinct channels; emissions during delivery wait for another batch."""
    signal, other = Signal("same"), Signal("same")
    calls: list[int] = []

    @stage.on_message(signal)
    def receive() -> None:
        calls.append(1)
        if len(calls) < 3:
            stage.broadcast(signal)

    stage.broadcast(other)
    _deliver(stage)
    assert calls == []
    stage.broadcast(signal)
    _deliver(stage)
    assert calls == [1]
    _deliver(stage)
    assert calls == [1, 1]
    _deliver(stage)
    assert calls == [1, 1, 1]


def test_script_failure_preserves_exception_and_cleans(stage: Stage) -> None:
    """User exceptions survive runner cleanup and all actor associations are released."""
    hero = actor(stage)

    async def fail(target: Sprite) -> None:
        await target.glide_by(x=1, seconds=0)
        raise LookupError("original")

    stage._target = pygame.display.set_mode((10, 10))
    hero.act(Script(fail))

    async def exercise() -> None:
        with pytest.raises(LookupError, match="original"):
            await drive(stage)

    asyncio.run(exercise())
    assert not stage._runs and hero._stage is None and stage._state == "closed"


def test_unsupported_asyncio_and_self_stop(stage: Stage) -> None:
    """Foreign awaits fail clearly; self-cancellation closes at the next boundary."""
    hero = actor(stage)

    async def bad(target: Sprite) -> None:
        await asyncio.sleep(0)

    hero.act(Script(bad))
    with pytest.raises(StageError, match="Plocks operations"):
        _step(stage)
    hero.stop()

    async def stop(target: Sprite) -> None:
        target.stop()
        await stage.wait(1)
        target.x = 999

    hero.act(Script(stop))
    _step(stage)
    assert not stage._runs and hero.x == 0


def test_sound_wait_cancellation(stage: Stage) -> None:
    """Canceling a waiting sound stops only its occurrence."""
    hero = actor(stage)
    sound = Sound(Path(__file__).parent.parent / "examples/proof/assets/tone.ogg")
    other = stage.play(sound, loop=True)
    hero.act(PlaySound(sound))
    _step(stage)
    own = stage._voices[-1]
    hero.stop()
    assert own.finished and not other.finished


def test_limits_do_not_leak_coroutines(stage: Stage) -> None:
    """Root and message admission have explicit finite limits."""
    hero = actor(stage)
    for _ in range(128):
        hero.act(Wait(10))
    with pytest.raises(StageError, match="128"):
        hero.act(Wait(10))
    signal = Signal("limit")
    for _ in range(256):
        stage.broadcast(signal)
    with pytest.raises(StageError, match="256"):
        stage.broadcast(signal)


def test_paused_callbacks_can_resume(stage: Stage) -> None:
    """Sync input continues while script execution and animation are frozen."""
    hero = actor(stage)
    hero.act(GlideBy(x=60, seconds=1))
    _step(stage)
    ticks(stage, 10)
    stage.pause()
    before = hero.x
    ticks(stage, 10)
    assert hero.x == before
    stage.on_key_down(Key.P)(stage.resume)
    stage._pending.append(Key.P)
    dispatch(stage)
    ticks(stage, 10)
    assert hero.x > before


def test_startup_binding_and_async_click(stage: Stage) -> None:
    """Callback decorators preserve their signatures while startup and click blocks share execution."""
    from plocks import MouseButton, Point
    from plocks._scripts import _trigger

    hero = actor(stage)
    stage._state = "new"
    stage.on_start(hero, Move(3))
    stage._state = "running"
    for handler in tuple(stage._starts):
        _trigger(stage, handler)
    _step(stage)
    assert hero.x == 3

    @stage.on_click
    async def clicked(position: Point, button: MouseButton) -> None:
        if button is MouseButton.LEFT:
            await hero.glide_to(x=position[0], seconds=0)

    stage._pending.append(((20.0, 10.0), MouseButton.LEFT))
    dispatch(stage)
    _step(stage)
    assert hero.x == 20
    ticks(stage, 1)
    assert not stage._runs


def test_during_early_background_and_parent_cancel(stage: Stage) -> None:
    """An early background can finish; stopping a parent closes its live children."""
    hero = actor(stage)
    recipe = During(GlideBy(x=60, seconds=1), meanwhile=Wait(0.1))
    hero.act(recipe)
    _step(stage)
    ticks(stage, 12)
    assert hero.x == 12 and len(stage._runs) == 1
    hero.stop()
    frozen = hero.position
    ticks(stage, 60)
    assert hero.position == frozen and not stage._runs


def test_visual_conflict_cancels_whole_root(stage: Stage) -> None:
    """Replacing a visual writer also closes the movement branch of its enclosing During."""
    hero = actor(stage)
    recipe = During(GlideBy(x=60, seconds=1), meanwhile=Loop(Costumes((hero.costume,), fps=5)))
    hero.act(recipe)
    _step(stage)
    ticks(stage, 10)
    hero.costume = Image.new("RGBA", (4, 4), "blue")
    frozen = hero.x
    ticks(stage, 60)
    assert hero.x == frozen and not stage._runs


def test_message_join_no_receivers_and_cancelled_receiver(stage: Stage) -> None:
    """Empty joins finish after delivery; accepted receiver cancellation also releases the sender."""
    sender, receiver = actor(stage), actor(stage)
    empty = Signal("empty")
    sender.act(Sequence(BroadcastAndWait(empty), Move(2)))
    _step(stage)
    assert sender.x == 0
    ticks(stage, 1)
    assert sender.x == 2
    signal = Signal("wait")
    stage.on_message(signal, receiver, Wait(10))
    sender.act(Sequence(BroadcastAndWait(signal), Move(3)))
    _step(stage)
    ticks(stage, 1)
    receiver.stop()
    ticks(stage, 1)
    assert sender.x == 5


def test_cancel_sender_does_not_cancel_receiver(stage: Stage) -> None:
    """A delivery has independent accepted invocations even when its sender stops waiting."""
    sender, receiver = actor(stage), actor(stage)
    signal = Signal("continue")
    stage.on_message(signal, receiver, Sequence(Wait(0.1), Move(4)))
    sender.act(BroadcastAndWait(signal))
    _step(stage)
    ticks(stage, 1)
    sender.stop()
    ticks(stage, 10)
    assert receiver.x == 4 and not stage._runs


def test_message_restart_factory_only_runs_for_accepted_invocations(stage: Stage) -> None:
    """Restart replaces the old root and captures the receiver's current location."""
    receiver = actor(stage)
    message = Message[int]("push")
    calls: list[int] = []

    def factory(amount: int) -> Block[Sprite]:
        calls.append(amount)
        return GlideBy(x=amount, seconds=1)

    stage.on_message(message, receiver, factory, when_busy=WhenBusy.RESTART)
    stage.broadcast(message, 60)
    ticks(stage, 1)
    ticks(stage, 15)
    before = receiver.x
    stage.broadcast(message, 30)
    ticks(stage, 1)
    ticks(stage, 60)
    assert calls == [60, 30]
    assert receiver.x == pytest.approx(before + 1 + 30)


def test_recipe_identity_restart_and_rebinding(stage: Stage) -> None:
    """The same active object deduplicates; removal cancels but preserves its event binding."""
    hero = actor(stage)
    recipe = GlideBy(x=60, seconds=1)
    hero.act(recipe)
    _step(stage)
    ticks(stage, 10)
    hero.act(recipe)
    assert len(stage._runs) == 1
    hero.act(recipe, restart=True)
    _step(stage)
    ticks(stage, 60)
    assert hero.x == 70
    stage.on_key_down(Key.SPACE, hero, recipe)
    stage.remove(hero)
    stage._pending.append(Key.SPACE)
    dispatch(stage)
    assert not stage._runs
    stage.add(hero)
    stage._pending.append(Key.SPACE)
    dispatch(stage)
    assert len(stage._runs) == 1


def test_immediate_budget_and_child_limit(stage: Stage) -> None:
    """Large finite repetitions yield, and structured children count toward the same cap."""
    hero = actor(stage)
    hero.act(Repeat(1000, Move(1)))
    _step(stage)
    assert 0 < hero.x < 1000
    ticks(stage, 30)
    assert hero.x == 1000
    tree: Block[Sprite] = Wait(10)
    for _ in range(65):
        tree = During(tree, meanwhile=Wait(10))
    hero.act(tree)
    with pytest.raises(StageError, match="128"):
        _step(stage)


def test_primary_failure_survives_cleanup_failure(stage: Stage) -> None:
    """Failing finally code cannot mask the original failure or skip other resources."""
    hero = actor(stage)

    async def cleanup_failure(target: Sprite) -> None:
        try:
            await stage.wait(10)
        finally:
            raise RuntimeError("cleanup")

    async def original_failure(target: Sprite) -> None:
        await stage.wait(0)
        raise LookupError("primary")

    stage._target = pygame.display.set_mode((10, 10))
    hero.act(Script(cleanup_failure))
    hero.act(Script(original_failure))

    async def exercise() -> None:
        with pytest.raises(LookupError, match="primary") as failure:
            await drive(stage)
        assert any("cleanup" in note for note in failure.value.__notes__)

    asyncio.run(exercise())
    assert stage._target is None and not stage._runs and hero._stage is None


def test_actor_single_membership_and_closed_admission(stage: Stage) -> None:
    """Membership has one owner and closed stages reject new execution."""
    hero = actor(stage)
    with pytest.raises(StageError):
        Stage().add(hero)
    stage.stop()
    with pytest.raises(StageError):
        hero.act(Wait(1))


def test_owned_fields_match_the_approved_model(stage: Stage) -> None:
    """Execution records have no progress/status copies or hidden writer indexes."""
    from plocks import Puppet
    from plocks._operations import _BubbleRun, _CostumeRun, _Delivery, _During, _Glide, _PoseRun
    from plocks._scripts import _Fiber, _Handler, _Run

    expected = {
        _BubbleRun: {"actor", "definition", "deadline"},
        _Fiber: {"coroutine", "waiting"},
        _Handler: {"start", "actor", "block", "when_busy"},
        _Run: {"actor", "block", "handler", "fiber"},
        _Glide: {"actor", "x", "y", "started", "seconds", "easing"},
        _CostumeRun: {"actor", "definition", "started"},
        _PoseRun: {"actor", "definition", "started"},
        _During: {"foreground", "background"},
        _Delivery: {"message", "data", "receivers"},
    }
    for cls, names in expected.items():
        assert {f.name for f in fields(cls)} == names
    transform = {
        "_x",
        "_y",
        "_direction",
        "_scale",
        "_visible",
        "_layer",
        "_rotation_style",
        "_stage",
    }
    assert set(Sprite.__slots__) == transform | {"_visual", "_bubble"}
    assert set(Puppet.__slots__) == transform | {"_skeleton", "_parts", "_pose", "_bubble"}
    assert set(Stage.__slots__) == {
        "_bubble_text_size",
        "_width",
        "_height",
        "_tick_rate",
        "_background",
        "_camera",
        "_volume",
        "_members",
        "_keyboard",
        "_mouse",
        "_pending",
        "_updates",
        "_draws",
        "_state",
        "_pause_reasons",
        "_tick",
        "_accumulator",
        "_last_wall",
        "_voices",
        "_target",
        "_task",
        "_keys",
        "_clicks",
        "_starts",
        "_message_handlers",
        "_runs",
        "_messages",
    }


def test_finite_extreme_motion_and_sampling(stage: Stage) -> None:
    """Finite opposite endpoints do not overflow an interpolation subtraction."""
    sprite = actor(stage)
    sprite.x = -1e308
    sprite.act(GlideTo(x=1e308, seconds=1))
    _step(stage)
    ticks(stage, 30)
    assert sprite.x == 0
    ticks(stage, 30)
    assert sprite.x == 1e308
    with pytest.raises(ValueError, match="duration"):
        Costumes((sprite.costume,), fps=5e-324)
    sprite.act(Costumes((sprite.costume,), fps=1e308))
    _step(stage)
    ticks(stage, 1)
    assert not stage._runs


def test_closed_stage_rejects_callback_registration(stage: Stage) -> None:
    """Closure cannot retain newly registered update or drawing callbacks."""
    from plocks import Canvas

    def update(dt: float) -> None:
        pass

    def draw(canvas: Canvas) -> None:
        pass

    close(stage)
    with pytest.raises(StageError):
        stage.on_update(update)
    with pytest.raises(StageError):
        stage.on_draw(draw)


def test_conditions_sample_when_reached(stage: Stage) -> None:
    """Queued recipes test current input/collision, not construction-time values."""
    from plocks import If, KeyDown, Touching

    hero, friend = actor(stage), actor(stage)
    friend.x = 10
    hero.act(
        Sequence(
            Wait(1 / 60),
            If(KeyDown(Key.RIGHT), then=Move(10), otherwise=Move(-10)),
            If(Touching(friend), then=GlideBy(y=5, seconds=0)),
        )
    )
    _step(stage)
    stage.keyboard._down.add(Key.RIGHT)
    ticks(stage, 1)
    assert hero.position == (10, 5)
    ticks(stage, 1)
    assert not stage._runs


def test_startup_stop_prevents_remaining_callbacks(stage: Stage) -> None:
    """Stopping in the first startup callback cannot invoke later snapshot handlers."""
    stage._state = "new"
    called: list[str] = []

    @stage.on_start
    def stop_immediately() -> None:
        stage.stop()

    @stage.on_start
    def never_started() -> None:
        called.append("unexpected")

    stage.run()
    assert not called and not stage.running
