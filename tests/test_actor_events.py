"""Actor registration shares Stage delivery, typing, and lifecycle semantics."""

from collections.abc import Callable, Iterator

import pytest
from PIL import Image

from plocks import (
    Actor,
    Block,
    GlideBy,
    Key,
    Message,
    Move,
    Puppet,
    Sequence,
    Signal,
    Sprite,
    Stage,
    StageError,
    Wait,
    WhenBusy,
)
from plocks._runtime import close, dispatch
from plocks._scripts import _deliver, _sample, _step, _trigger


@pytest.fixture(params=["sprite", "puppet"])
def actor(request: pytest.FixtureRequest) -> Actor:
    """Exercise both concrete actor APIs without a shared actor base class."""
    return Sprite(Image.new("RGBA", (8, 8))) if request.param == "sprite" else Puppet.stick_figure()


@pytest.fixture
def stage() -> Iterator[Stage]:
    """Keep resources and admitted coroutines within the test's lifetime."""
    value = Stage()
    yield value
    close(value)


def advance(stage: Stage, count: int) -> None:
    """Advance exact simulation ticks in the engine's dispatch order."""
    for _ in range(count):
        if not stage.paused:
            stage._tick += 1
            _sample(stage)
            _deliver(stage)
            dispatch(stage)
            _step(stage)


def test_attached_startup_only(actor: Actor, stage: Stage) -> None:
    """Registration requires attachment and startup cannot be registered late."""
    registrations: tuple[Callable[[], None], ...] = (
        lambda: actor.on_start(Move(1)),
        lambda: actor.on_key_down(Key.SPACE, Move(1)),
        lambda: actor.on_message(Signal("go"), Move(1)),
    )
    for register in registrations:
        with pytest.raises(StageError, match="Add the actor"):
            register()
    stage.add(actor)
    actor.on_start(Move(12))
    assert actor.x == 0 and not stage._runs
    stage._state = "running"
    for handler in tuple(stage._starts):
        _trigger(stage, handler)
    _step(stage)
    assert actor.x == 12
    with pytest.raises(StageError, match="before run"):
        actor.on_start(Move(1))
    stage.remove(actor)
    stage.add(actor)
    advance(stage, 1)
    assert actor.x == 12


@pytest.mark.parametrize("busy", [WhenBusy.IGNORE, WhenBusy.RESTART])
def test_key_busy_pause_and_independent_motion(actor: Actor, stage: Stage, busy: WhenBusy) -> None:
    """A game-wide key admits independent actors and preserves busy/pause rules."""
    stage.add(actor)
    friend = Sprite(Image.new("RGBA", (4, 4)))
    stage.add(friend)
    actor.on_key_down(Key.SPACE, GlideBy(y=60, seconds=1), when_busy=busy)
    friend.on_key_down(Key.SPACE, Move(2))
    stage._state = "running"
    stage.pause()
    stage._pending.append(Key.SPACE)
    dispatch(stage)
    assert len(stage._runs) == 2 and actor.y == 0 and friend.x == 0
    stage.resume()
    _step(stage)
    advance(stage, 30)
    assert actor.y == 30 and friend.x == 2
    original = stage._runs[0]
    stage._pending.append(Key.SPACE)
    dispatch(stage)
    _step(stage)
    assert friend.x == 4
    assert (stage._runs[0] is original) == (busy is WhenBusy.IGNORE)
    advance(stage, 60)
    assert actor.y == (60 if busy is WhenBusy.IGNORE else 90)
    assert not stage._runs


def test_signal_and_typed_factory(actor: Actor, stage: Stage) -> None:
    """Payload factories are deferred and skipped busy deliveries never evaluate them."""
    signal = Signal("go")
    message = Message[int]("distance")
    received: list[int] = []

    def recipe(distance: int) -> Block[Actor]:
        received.append(distance)
        return Sequence(Move(distance), Wait(1))

    stage.add(actor)
    actor.on_message(signal, Move(2))
    actor.on_message(message, recipe)
    stage._state = "running"
    stage.broadcast(signal)
    stage.broadcast(message, 5)
    _deliver(stage)
    assert received == [] and actor.x == 0
    _step(stage)
    assert received == [5] and actor.x == 7
    stage.broadcast(message, 99)
    _deliver(stage)
    _step(stage)
    assert received == [5]
    actor.stop()
    stage.broadcast(message, 3)
    _deliver(stage)
    _step(stage)
    assert received == [5, 3] and actor.x == 10


def test_registration_stays_with_its_stage(actor: Actor, stage: Stage) -> None:
    """Removal cancels runs, re-add activates old handlers, and migration never moves them."""
    signal = Signal("go")
    stage.add(actor)
    actor.on_key_down(Key.SPACE, GlideBy(x=60, seconds=1))
    actor.on_message(signal, Move(3))
    stage._state = "running"
    stage._pending.append(Key.SPACE)
    dispatch(stage)
    _step(stage)
    advance(stage, 10)
    stage.remove(actor)
    frozen = actor.x
    assert not stage._runs
    stage._pending.append(Key.SPACE)
    stage.broadcast(signal)
    dispatch(stage)
    _deliver(stage)
    assert not stage._runs
    other = Stage()
    try:
        other.add(actor)
        other._state = "running"
        actor.on_key_down(Key.SPACE, Move(4))
        stage._pending.append(Key.SPACE)
        dispatch(stage)
        other._pending.append(Key.SPACE)
        dispatch(other)
        _step(other)
        assert actor.x == frozen + 4 and not stage._runs
        other.remove(actor)
        stage.add(actor)
        stage.broadcast(signal)
        _deliver(stage)
        _step(stage)
        assert actor.x == frozen + 7
    finally:
        close(other)
    close(stage)
    assert actor._stage is None and not stage._keys and not stage._message_handlers
    with pytest.raises(StageError):
        actor.on_key_down(Key.SPACE, Move(1))


def test_factory_error_remains_original(actor: Actor, stage: Stage) -> None:
    """Actor registration does not wrap an exception raised by a message factory."""
    failure = ValueError("original factory failure")
    message = Message[int]("bad")

    def fail(value: int) -> Block[Actor]:
        raise failure

    stage.add(actor)
    actor.on_message(message, fail)
    stage._state = "running"
    stage.broadcast(message, 1)
    _deliver(stage)
    with pytest.raises(ValueError) as caught:
        _step(stage)
    assert caught.value is failure
