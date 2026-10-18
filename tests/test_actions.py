"""Action identity, dependencies and structured callback ownership."""

from collections.abc import Iterator

import pytest
from PIL import Image

from plocks import Action, Event, Key, Sprite, Stage, StageError
from plocks._runtime import close, dispatch
from plocks._scripts import _sample, _step


@pytest.fixture
def stage() -> Iterator[Stage]:
    value = Stage()
    value._state = "running"
    yield value
    close(value)


def sprite(stage: Stage) -> Sprite:
    actor = Sprite(Image.new("RGBA", (4, 4), "red"))
    stage.add(actor)
    return actor


def ticks(stage: Stage, count: int) -> None:
    for _ in range(count):
        if not stage.paused:
            _step(stage)
            stage._tick += 1
            _sample(stage)


def test_after_captures_position_on_start(stage: Stage) -> None:
    actor = sprite(stage)
    first = actor.glide_by(x=30, seconds=0.3)
    last = actor.glide_by(x=30, seconds=0.3, after=first)
    assert actor.x == 0 and not first.done
    ticks(stage, 37)
    assert actor.x == pytest.approx(60)
    assert first.done and last.done and not last.cancelled
    assert not stage._actions


def test_callback_adopts_chain_and_busy_ignores(stage: Stage) -> None:
    actor = sprite(stage)
    calls = 0

    @actor.on_key_down(Key.SPACE)
    def jump(event: Event[Sprite, Key]) -> Action:
        actor = event.target
        nonlocal calls
        calls += 1
        up = actor.glide_by(y=100, seconds=0.3)
        return actor.glide_by(y=-100, seconds=0.3, after=up)

    stage._pending.append(Key.SPACE)
    dispatch(stage)
    ticks(stage, 10)
    stage._pending.append(Key.SPACE)
    dispatch(stage)
    assert calls == 1 and actor.y > 0
    actor.stop()
    assert not stage._actions
    ticks(stage, 60)
    assert actor.y > 0


def test_cancel_propagates_only_to_dependents(stage: Stage) -> None:
    actor = sprite(stage)
    first = actor.glide_by(x=100, seconds=1)
    second = actor.glide_by(x=100, seconds=1, after=first)
    independent = actor.glide_by(y=100, seconds=1)
    ticks(stage, 10)
    first.cancel()
    assert first.cancelled and second.cancelled and not independent.done
    ticks(stage, 60)
    assert independent.done and actor.y == 100


def test_callback_return_observes_one_execution(stage: Stage) -> None:
    actor = sprite(stage)
    existing = actor.glide_by(x=30, seconds=0.3)

    @actor.on_key_down(Key.A)
    def move(event: Event[Sprite, Key]) -> Action:
        return existing

    stage._pending.append(Key.A)
    dispatch(stage)
    ticks(stage, 45)
    assert actor.x == 30 and not stage._actions
    assert not hasattr(existing, "__await__")


def test_pause_and_invalid_admission(stage: Stage) -> None:
    actor = sprite(stage)
    action = actor.glide_by(x=10, seconds=1)
    stage.pause()
    ticks(stage, 100)
    assert actor.x == 0 and not action.done
    stage.resume()
    with pytest.raises(ValueError):
        actor.glide_by(x=float("nan"), seconds=1)
    foreign = Stage()
    other = sprite(foreign)
    try:
        with pytest.raises(StageError, match="same stage"):
            other.glide_by(x=1, seconds=1, after=action)
    finally:
        close(foreign)
    ticks(stage, 61)
    assert action.done and actor.x == 10


def test_failure_is_observed_and_cleanup_retires_children(stage: Stage) -> None:
    actor = sprite(stage)
    error = ValueError("original")

    @actor.on_key_down(Key.A)
    def fail(event: Event[Sprite, Key]) -> None:
        actor.glide_by(x=100, seconds=1)
        raise error

    stage._pending.append(Key.A)
    with pytest.raises(ValueError) as caught:
        dispatch(stage)
    close(stage)
    assert caught.value is error and not stage._actions
