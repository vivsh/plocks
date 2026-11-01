"""Simulation timers, derived clone counts and detached clone-end callbacks."""

from collections.abc import Iterator
from unittest.mock import patch

import pytest

from plocks import Action, BodyType, Event, Image, Puppet, Script, Sprite, Stage, WhenBusy
from plocks._runtime import advance, close
from plocks._scripts import _step


def tick(stage: Stage, count: int = 1) -> None:
    for _ in range(count):
        advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)


@pytest.fixture
def stage() -> Iterator[Stage]:
    game = Stage(physics=True)
    game._state = "running"
    game._last_wall = 0
    yield game
    close(game)


@pytest.mark.parametrize("puppet", [False, True])
def test_clone_counts_start_end_and_descendants(stage: Stage, puppet: bool) -> None:
    actor = Puppet.stick_figure() if puppet else Sprite(Image.rectangle(10, 10))
    stage.add(actor)
    starts: list[Sprite | Puppet] = []
    ends: list[tuple[Sprite | Puppet, int, int]] = []

    def start(event: Event[Sprite | Puppet, None]) -> None:
        starts.append(event.target)
        assert event.source is event.target._clone_source

    def end(event: Event[Sprite | Puppet, None]) -> None:
        assert event.target._stage is None
        assert event.source is event.target._clone_source
        ends.append((event.target, actor.clone_count, stage.clone_count))
        event.target.remove()

    if isinstance(actor, Sprite):
        actor.on_clone_start(start)
        actor.on_clone_end(end)
    else:
        actor.on_clone_start(start)
        actor.on_clone_end(end)

    first, second = actor.clone(), actor.clone()
    nested = first.clone()
    assert actor.clone_count == 2 and first.clone_count == 1 and stage.clone_count == 3
    tick(stage)
    assert starts == [first, second, nested]
    second.remove()
    assert ends == [(second, 1, 2)]
    second.remove()
    assert len(ends) == 1
    first.remove()
    assert actor.clone_count == 0 and stage.clone_count == 1
    assert first.is_clone and first.clone_count == 0
    assert nested._stage is stage
    close(stage)
    assert len(ends) == 2


def test_clone_end_can_replace_without_global_stage(stage: Stage) -> None:
    source = Sprite(Image.rectangle(10, 10))
    stage.add(source)
    replacements: list[Sprite] = []

    @source.on_clone_end
    def ended(event: Event[Sprite, None]) -> None:
        assert source.clone_count == 0
        replacements.append(source.clone())

    source.clone().remove()
    assert source.clone_count == stage.clone_count == len(replacements) == 1


def test_failed_clone_does_not_emit_end(stage: Stage) -> None:
    source = Sprite(Image.rectangle(10, 10))
    stage.add(source)
    ends: list[Sprite] = []

    @source.on_clone_end
    def ended(event: Event[Sprite, None]) -> None:
        ends.append(event.target)

    from plocks import _cloning

    original = _cloning._inherit

    def fail(game: Stage, actor: Sprite | Puppet, clone: Sprite | Puppet) -> None:
        original(game, actor, clone)
        raise RuntimeError("failed construction")

    with patch.object(_cloning, "_inherit", side_effect=fail), pytest.raises(RuntimeError):
        source.clone()
    assert ends == [] and stage.clone_count == source.clone_count == 0
    assert len(stage._clone_end_handlers) == 1


def test_clone_end_error_occurs_after_cleanup(stage: Stage) -> None:
    source = Sprite(Image.rectangle(10, 10))
    stage.add(source)

    @source.on_clone_end
    def ended(event: Event[Sprite, None]) -> None:
        assert event.target._stage is None and source.clone_count == 0
        raise RuntimeError("end failure")

    clone = source.clone()
    with pytest.raises(RuntimeError, match="end failure"):
        clone.remove()
    assert clone._stage is None and source._stage is stage and stage.clone_count == 0
    assert not stage.running


def test_remove_after_pause_cancel_readd_and_script_self_removal(stage: Stage) -> None:
    actor = Sprite(Image.rectangle(10, 10), body_type=BodyType.NONE)
    stage.add(actor)
    canceled = actor.remove_after(seconds=0.1)
    canceled.cancel()
    tick(stage, 10)
    assert actor._stage is stage
    removal = actor.remove_after(seconds=0.1)
    tick(stage, 3)
    stage.pause()
    tick(stage, 100)
    assert actor._stage is stage and not removal.done
    stage.resume()
    tick(stage, 10)
    assert actor._stage is None and removal.cancelled
    stage.add(actor)
    tick(stage, 20)
    assert actor._stage is stage
    action = actor.act(Script().wait(0.02).remove().move(100))
    tick(stage, 5)
    assert actor._stage is None and actor.x == 0 and action.cancelled


def test_every_phase_pause_and_subtick_fairness(stage: Stage) -> None:
    times: list[float] = []

    @stage.every(seconds=0.025)
    def repeat(event: Event[Stage, float]) -> None:
        assert event.data == 0.025 and event.target is stage
        times.append(stage.time)

    _step(stage)
    tick(stage, 31)
    assert len(times) == 20
    assert times[-1] == pytest.approx(0.5)
    stage.pause()
    tick(stage, 100)
    assert len(times) == 20
    stage.resume()
    tick(stage, 5)
    assert 22 <= len(times) <= 23

    small: list[float] = []

    @stage.every(seconds=0.00001)
    def fast(event: Event[Stage, float]) -> None:
        small.append(stage.time)

    tick(stage, 10)
    assert 8 <= len(small) <= 10
    assert len(set(small)) == len(small)


@pytest.mark.parametrize("policy", [WhenBusy.IGNORE, WhenBusy.RESTART])
def test_every_busy_and_closure(stage: Stage, policy: WhenBusy) -> None:
    actor = Sprite(Image.rectangle(10, 10), body_type=BodyType.NONE)
    stage.add(actor)
    actions: list[Action] = []

    @stage.every(seconds=0.05, when_busy=policy)
    def repeat(event: Event[Stage, float]) -> Action:
        action = actor.wait(0.2)
        actions.append(action)
        return action

    tick(stage, 40)
    assert len(actions) >= 2
    if policy is WhenBusy.RESTART:
        assert len(actions) >= 10 and any(action.cancelled for action in actions)
    else:
        assert len(actions) <= 4
    close(stage)
    assert not stage._actions and all(action.done for action in actions)


def test_periodic_callback_errors_are_observed(stage: Stage) -> None:
    @stage.every(seconds=0.01)
    def fail(event: Event[Stage, float]) -> None:
        raise LookupError("timer failure")

    with pytest.raises(LookupError, match="timer failure"):
        tick(stage, 5)
    close(stage)
    assert not stage._actions


def test_end_before_run_and_before_start_is_once() -> None:
    game = Stage()
    source = Sprite(Image.rectangle(10, 10))
    game.add(source)
    ends: list[Sprite] = []
    starts: list[Sprite] = []

    @source.on_clone_start
    def started(event: Event[Sprite, None]) -> None:
        starts.append(event.target)

    @source.on_clone_end
    def ended(event: Event[Sprite, None]) -> None:
        ends.append(event.target)

    try:
        clone = source.clone()
        clone.remove()
        clone.remove()
        assert ends == [clone] and starts == []
        assert not game._pending and source.clone_count == game.clone_count == 0
    finally:
        close(game)


def test_minimum_positive_timer_is_bounded(stage: Stage) -> None:
    occurrences: list[float] = []

    @stage.every(seconds=5e-324)
    def fast(event: Event[Stage, float]) -> None:
        occurrences.append(stage.time)

    tick(stage, 10)
    assert 1 <= len(occurrences) <= 10
    assert len(set(occurrences)) == len(occurrences)


def test_script_walk_during_glide_rejects_same_axis(stage: Stage) -> None:
    actor = Sprite(Image.rectangle(10, 10), body_type=BodyType.KINEMATIC)
    stage.add(actor)
    actor.act(
        Script().during(Script().glide_by(x=20, seconds=1), meanwhile=Script().walk(speed=20))
    )
    from plocks import StageError

    with pytest.raises(StageError, match="same property"):
        tick(stage)


def test_live_fiber_limit_applies_to_timer_registration(stage: Stage) -> None:
    from plocks import StageError

    def idle(event: Event[Stage, float]) -> None:
        pass

    for _ in range(128):
        stage.every(seconds=1)(idle)
    with pytest.raises(StageError, match="128"):
        stage.every(seconds=1)(idle)
    assert len(stage._actions) == 128


def test_exact_added_ownership() -> None:
    from dataclasses import fields

    from plocks import Body
    from plocks._commands import _Jump, _MoveCell, _Remove, _Walk
    from plocks._operations import _CellMove

    assert {f.name for f in fields(_CellMove)} == {
        "actor",
        "world",
        "origin",
        "destination",
        "started",
        "seconds",
    }
    assert {f.name for f in fields(_Walk)} == {"speed"}
    assert {f.name for f in fields(_Jump)} == {"height"}
    assert {f.name for f in fields(_Remove)} == set()
    assert {f.name for f in fields(_MoveCell)} == {"world", "direction", "seconds"}
    assert set(Body.__slots__) == {
        "_actor",
        "_world",
        "_native",
        "_shape",
        "_auto_shape",
        "_boundary_native",
        "_drag",
        "_collision_group",
        "_collides_with",
        "_projectile",
    }
    for actor_type in (Sprite, Puppet):
        assert "_clone_source" in actor_type.__slots__
        assert "_is_clone" not in actor_type.__slots__


def test_runtime_timer_starts_from_registration_time(stage: Stage) -> None:
    tick(stage, 30)
    registered = stage.time
    times: list[float] = []

    @stage.every(seconds=0.05)
    def pulse(event: Event[Stage, float]) -> None:
        times.append(stage.time)

    # Skip the immediate script phase, as if registration happened in on_update.
    stage._tick += 1
    tick(stage, 3)
    assert times == [pytest.approx(registered + 0.05)]


def test_failed_clone_clears_inherited_touch_watches(stage: Stage) -> None:
    from plocks import _cloning

    source = Sprite(Image.rectangle(10, 10))
    target = Sprite(Image.rectangle(10, 10), x=20)
    stage.add(source)
    stage.add(target)

    @source.on_touch(target)
    def touch(event: Event[Sprite, Sprite]) -> None:
        pass

    @source.on_clone_end
    def ended(event: Event[Sprite, None]) -> None:
        raise AssertionError("Rollback must not emit clone end")

    original = _cloning._inherit

    def fail(owner: Stage, actor: Sprite | Puppet, clone: Sprite | Puppet) -> None:
        original(owner, actor, clone)
        raise RuntimeError("rollback")

    with patch.object(_cloning, "_inherit", side_effect=fail), pytest.raises(RuntimeError):
        source.clone()
    assert stage.clone_count == 0
    assert len(stage._touches) == 1 and stage._touches[0].actor is source
    assert len(stage._clone_end_handlers) == 1
