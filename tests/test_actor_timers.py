"""Actor periodic callbacks share the simulation clock and receiver lifecycle."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import cast
from unittest.mock import patch

import pytest

from plocks import (
    Action,
    Actor,
    Bounds,
    Event,
    Image,
    Joint,
    Message,
    Puppet,
    Script,
    Skeleton,
    Sprite,
    Stage,
    StageError,
    WhenBusy,
)
from plocks._runtime import advance, close
from plocks._scripts import _count


def tick(stage: Stage, count: int = 1) -> None:
    for _ in range(count):
        advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)


@dataclass
class EnemyState:
    pulses: int = 0


def test_first_periodic_sprite_and_independent_motion() -> None:
    stage = Stage()
    enemy = Sprite(Image.rectangle(20, 20), state=EnemyState)
    friend = Sprite(Image.circle(8), x=-100)
    stage.add(enemy)
    stage.add(friend)
    events: list[tuple[float, float]] = []

    @enemy.every(seconds=0.1)
    def pulse(event: Event[Sprite[EnemyState], float]) -> Action:
        assert event.source is stage and event.target is enemy and event.data == 0.1
        event.target.state.pulses += 1
        events.append((stage.time, friend.x))
        return event.target.say("Hello", seconds=0.02)

    stage._state, stage._last_wall = "running", 0.0
    try:
        motion = friend.glide_by(x=100, seconds=0.5)
        tick(stage, 5)
        assert not events and friend.x > -100
        tick(stage, 27)
        assert len(events) == 5 and enemy.state.pulses == 5
        assert events[0][0] == pytest.approx(0.1)
        assert motion.done and friend.x == 0
        assert all(
            timer.action is not None and timer.action._actor is None for timer in stage._timers
        )
    finally:
        close(stage)
    assert not stage._timers and not stage._actions


@pytest.fixture
def stage() -> Iterator[Stage]:
    owner = Stage()
    owner._state, owner._last_wall = "running", 0.0
    yield owner
    close(owner)
    assert not owner._timers and not owner._actions


def actor(stage: Stage, puppet: bool = False) -> Actor:
    picture = Image.rectangle(12, 12)
    result = (
        Puppet(Skeleton({"root": Joint(None)}), parts={"root": picture})
        if puppet
        else Sprite(picture)
    )
    stage.add(result)
    return result


def bind(
    receiver: Actor,
    callback: Callable[[Event[Actor, float]], None | Action | Script[Actor]],
    *,
    seconds: float = 0.1,
    when_busy: WhenBusy = WhenBusy.IGNORE,
) -> None:
    if isinstance(receiver, Sprite):
        receiver.every(seconds=seconds, when_busy=when_busy)(callback)
    else:
        receiver.every(seconds=seconds, when_busy=when_busy)(callback)


@pytest.mark.parametrize("puppet", [False, True])
def test_fractional_phase_pause_and_subtick_fairness(stage: Stage, puppet: bool) -> None:
    receiver = actor(stage, puppet)
    times: list[float] = []

    def pulse(event: Event[Actor, float]) -> None:
        assert event.source is stage and event.target is receiver and event.data == 0.025
        times.append(stage.time)

    bind(receiver, pulse, seconds=0.025)
    tick(stage, 31)
    assert len(times) == 20 and times[-1] == pytest.approx(0.5)
    for reason in ("user", "focus", "alert"):
        stage._set_pause(reason, True)
        before = stage.time, len(times)
        tick(stage, 30)
        assert (stage.time, len(times)) == before
        stage._set_pause(reason, False)
        tick(stage, 4)
    small: list[float] = []
    bind(receiver, lambda event: small.append(stage.time), seconds=5e-324)
    tick(stage, 20)
    assert 18 <= len(small) <= 20 and len(set(small)) == len(small)


@pytest.mark.parametrize("puppet", [False, True])
@pytest.mark.parametrize("policy", list(WhenBusy))
def test_busy_policies_and_stop_preserve_future_calls(
    stage: Stage, puppet: bool, policy: WhenBusy
) -> None:
    receiver = actor(stage, puppet)
    work: list[Action] = []

    def pulse(event: Event[Actor, float]) -> Action:
        action = event.target.wait(0.2)
        work.append(action)
        return action

    bind(receiver, pulse, seconds=0.05, when_busy=policy)
    driver = stage._timers[0].action
    tick(stage, 20)
    if policy is WhenBusy.IGNORE:
        assert len(work) == 2
    else:
        assert len(work) >= 6 and any(action.cancelled for action in work)
    receiver.stop()
    assert all(action.done for action in work)
    assert driver is stage._timers[0].action and driver is not None and not driver.done
    before = len(work)
    tick(stage, 5)
    assert len(work) > before


@pytest.mark.parametrize("puppet", [False, True])
def test_returned_scripts_run_on_the_receiver(stage: Stage, puppet: bool) -> None:
    receiver = actor(stage, puppet)

    def pulse(event: Event[Actor, float]) -> Script[Actor]:
        return Script().move(3)

    bind(receiver, pulse, seconds=0.05)
    tick(stage, 14)
    assert receiver.x == 12
    driver = stage._timers[0].action
    assert driver is not None and not driver.done


@pytest.mark.parametrize("puppet", [False, True])
def test_remove_stops_invocations_readd_starts_a_full_interval(stage: Stage, puppet: bool) -> None:
    receiver = actor(stage, puppet)
    calls: list[float] = []
    work: list[Action] = []

    def pulse(event: Event[Actor, float]) -> Action:
        calls.append(stage.time)
        result = event.target.wait(2)
        work.append(result)
        return result

    bind(receiver, pulse)
    definition = stage._timers[0]
    tick(stage, 8)
    assert len(calls) == 1 and not work[0].done
    old = definition.action
    receiver.remove()
    assert definition.action is None and old is not None and old.cancelled
    assert work[0].cancelled and len(stage._timers) == 1
    tick(stage, 30)
    assert len(calls) == 1 and _count(stage) == 0
    stage.add(receiver)
    assert definition.action is not old
    added = stage.time
    tick(stage, 5)
    assert len(calls) == 1
    tick(stage, 2)
    assert calls[-1] == pytest.approx(added + 0.1) and len(calls) == 2


@pytest.mark.parametrize("puppet", [False, True])
def test_removing_and_readding_inside_callback_cannot_revive_old_driver(
    stage: Stage, puppet: bool
) -> None:
    receiver = actor(stage, puppet)
    calls: list[float] = []
    drivers: list[Action | None] = []

    def pulse(event: Event[Actor, float]) -> None:
        calls.append(stage.time)
        drivers.append(stage._timers[0].action)
        event.target.remove()
        stage.add(event.target)

    bind(receiver, pulse, seconds=0.05)
    tick(stage, 20)
    assert len(calls) == 6 and len(set(calls)) == 6
    assert len(stage._timers) == _count(stage) == 1
    assert all(driver is not None and driver.cancelled for driver in drivers)
    assert stage._timers[0].action not in drivers


@pytest.mark.parametrize("puppet", [False, True])
def test_clone_inherits_independent_phase_and_registration_snapshot(
    stage: Stage, puppet: bool
) -> None:
    source = actor(stage, puppet)
    calls: list[tuple[Actor, float]] = []
    bind(source, lambda event: calls.append((event.target, stage.time)))
    tick(stage, 3)
    copy = source.clone()
    assert len(stage._timers) == 2
    assert stage._timers[0].handler is not stage._timers[1].handler
    assert stage._timers[0].action is not stage._timers[1].action
    tick(stage, 4)
    assert len(calls) == 1 and calls[0][0] is source
    assert calls[0][1] == pytest.approx(0.1)
    tick(stage, 3)
    assert calls[-1][0] is copy and calls[-1][1] == pytest.approx(0.15)
    late: list[Actor] = []
    bind(source, lambda event: late.append(event.target), seconds=0.05)
    tick(stage, 4)
    assert late and all(item is source for item in late)
    copy.remove()
    assert len(stage._timers) == 2 and all(timer.handler.actor is source for timer in stage._timers)
    after = len(calls)
    tick(stage, 12)
    assert all(target is source for target, _ in calls[after:])
    stage.add(copy)
    assert len(stage._timers) == 2  # Removed clones' registrations stay pruned.


def test_many_clone_cycles_do_not_leak_drivers_or_definitions(stage: Stage) -> None:
    source = actor(stage)
    bind(source, lambda event: None)
    for _ in range(150):
        copy = source.clone()
        assert len(stage._timers) == _count(stage) == 2
        copy.remove()
        assert len(stage._timers) == _count(stage) == 1
    assert source._stage is stage and stage.clone_count == 0


def test_clone_state_is_independent_and_preserves_receiver_typing(stage: Stage) -> None:
    source = Sprite(Image.rectangle(12, 12), state=EnemyState)
    stage.add(source)

    @source.every(seconds=0.05)
    def pulse(event: Event[Sprite[EnemyState], float]) -> None:
        event.target.state.pulses += 1

    copy = source.clone()
    tick(stage, 10)
    assert source.state is not copy.state
    assert source.state.pulses == copy.state.pulses == 3
    copy.remove()
    tick(stage, 3)
    assert source.state.pulses == 4 and copy.state.pulses == 3


def test_registration_from_a_handler_stays_stage_owned_after_stop(stage: Stage) -> None:
    from plocks._scripts import _trigger

    receiver = Sprite(Image.rectangle(10, 10))
    stage.add(receiver)
    pulses: list[Actor] = []
    message = Message[None]("install periodic callback")

    @receiver.on_broadcast(message)
    def install(event: Event[Sprite, None]) -> Script[Actor]:
        bind(event.target, lambda pulse: pulses.append(pulse.target), seconds=0.05)
        return Script().wait(5)

    handler = next(iter(stage._message_handlers.values()))[0]
    installer = _trigger(stage, handler)
    assert installer is not None and len(stage._timers) == 1
    driver = stage._timers[0].action
    assert driver is not None and driver._parent is None
    receiver.stop(installer)
    assert installer.cancelled and not driver.done
    tick(stage, 10)
    assert pulses == [receiver] * 3


def test_registration_from_a_timer_callback_survives_its_creator_removal(stage: Stage) -> None:
    first, second = actor(stage), actor(stage)
    calls: list[float] = []

    def install(event: Event[Actor, float]) -> None:
        bind(second, lambda pulse: calls.append(stage.time), seconds=0.05)
        first.remove()

    bind(first, install, seconds=0.05)
    tick(stage, 13)
    assert first._stage is None and second._stage is stage
    assert len(calls) == 3 and calls[0] == pytest.approx(0.1)
    assert stage._timers[0].action is None
    assert stage._timers[1].action is not None and stage._timers[1].action._parent is None


def test_detached_decorators_and_stage_changes_do_not_register(stage: Stage) -> None:
    receiver = Sprite(Image.rectangle(10, 10))
    with pytest.raises(StageError):
        receiver.every(seconds=1)
    stage.add(receiver)
    decorate = receiver.every(seconds=1)
    receiver.remove()
    with pytest.raises(StageError):
        decorate(lambda event: None)
    other = Stage()
    other.add(receiver)
    try:
        with pytest.raises(StageError, match="changed stages"):
            decorate(lambda event: None)
        assert not stage._timers and not other._timers
    finally:
        close(other)


def test_readd_to_another_stage_does_not_migrate_old_registrations(stage: Stage) -> None:
    receiver = actor(stage)
    pulses: list[Actor] = []
    bind(receiver, lambda event: pulses.append(event.target), seconds=0.05)
    receiver.remove()
    other = Stage()
    other._state, other._last_wall = "running", 0.0
    other.add(receiver)
    try:
        tick(other, 10)
        tick(stage, 10)
        assert not pulses and not other._timers
        receiver.remove()
        stage.add(receiver)
        tick(stage, 4)
        assert pulses == [receiver]
    finally:
        close(other)


@pytest.mark.parametrize("seconds", [0, -1, float("nan"), float("inf"), float("-inf"), True])
def test_invalid_intervals_are_rejected_without_mutation(stage: Stage, seconds: float) -> None:
    receiver = actor(stage)
    with pytest.raises((TypeError, ValueError)):
        receiver.every(seconds=seconds)
    assert not stage._timers and not stage._actions


def test_async_callbacks_and_invalid_busy_are_rejected(stage: Stage) -> None:
    receiver = actor(stage)

    async def invalid(event: Event[Actor, float]) -> None:
        pass

    wrong = cast(Callable[[Event[Actor, float]], None], invalid)
    with pytest.raises(TypeError, match="synchronous"):
        bind(receiver, wrong)
    with pytest.raises(TypeError, match="WhenBusy"):
        receiver.every(seconds=1, when_busy=cast(WhenBusy, "ignore"))
    assert not stage._timers and not stage._actions


def test_closed_and_failed_drivers_release_records_and_preserve_errors(stage: Stage) -> None:
    receiver = actor(stage)

    def fail(event: Event[Actor, float]) -> None:
        raise LookupError("actor timer failed")

    bind(receiver, fail, seconds=0.01)
    definition = stage._timers[0]
    with pytest.raises(LookupError, match="actor timer failed"):
        tick(stage, 3)
    assert definition.action is None
    close(stage)
    with pytest.raises(StageError):
        receiver.every(seconds=1)


def test_close_before_first_tick_releases_borrowed_queued_driver() -> None:
    owner = Stage()
    receiver = actor(owner)
    bind(receiver, lambda event: None)
    definition = owner._timers[0]
    driver = definition.action
    close(owner)
    close(owner)
    assert driver is not None and driver.cancelled and definition.action is None
    assert not owner._timers and receiver._stage is None


def test_readd_budget_failure_is_transactional(stage: Stage) -> None:
    receiver = actor(stage)
    bind(receiver, lambda event: None)
    receiver.remove()
    for _ in range(128):
        stage.wait(100)
    before = receiver.position, receiver._transform
    with pytest.raises(StageError, match="128-execution"):
        stage.add(receiver)
    assert receiver not in stage.objects and receiver._stage is None
    assert (receiver.position, receiver._transform) == before
    assert stage._timers[0].action is None and _count(stage) == 128


def test_failed_clone_cleans_partial_timer_inheritance(stage: Stage) -> None:
    from plocks import _cloning

    source = actor(stage)
    bind(source, lambda event: None)
    original = _cloning._inherit

    def fail(owner: Stage, original_actor: Actor, copy: Actor) -> None:
        original(owner, original_actor, copy)
        raise RuntimeError("clone rollback")

    with patch.object(_cloning, "_inherit", side_effect=fail), pytest.raises(RuntimeError):
        source.clone()
    assert source._stage is stage and stage.clone_count == 0
    assert len(stage._timers) == _count(stage) == 1
    assert stage._timers[0].handler.actor is source


def test_partial_readd_failure_retires_physics_and_retains_definitions() -> None:
    from plocks import _timers

    owner = Stage(physics=True)
    receiver = actor(owner)
    receiver.keep_inside(Bounds(-100, -100, 100, 100))
    bind(receiver, lambda event: None)
    bind(receiver, lambda event: None)
    receiver.remove()
    previous = receiver._transform
    original = _timers._start
    admitted = 0

    def fail(stage: Stage, timer: _timers._Timer) -> None:
        nonlocal admitted
        admitted += 1
        if admitted == 2:
            raise RuntimeError("restart rollback")
        original(stage, timer)

    try:
        with patch.object(_timers, "_start", side_effect=fail), pytest.raises(RuntimeError):
            owner.add(receiver)
        assert receiver._stage is None and receiver._transform is previous
        assert not owner.physics._bodies and not owner._actions
        assert owner.physics._space is not None and not owner.physics._space.shapes
        assert len(owner._timers) == 2 and all(timer.action is None for timer in owner._timers)
        owner.add(receiver)
        assert len(owner.physics._bodies) == 1 and _count(owner) == 2
    finally:
        close(owner)


def test_definition_limit_includes_detached_actors_and_rolls_back_clone(stage: Stage) -> None:
    receiver = actor(stage)
    bind(receiver, lambda event: None)
    receiver.remove()
    for _ in range(1023):
        other = actor(stage)
        bind(other, lambda event: None)
        other.remove()
    assert len(stage._timers) == 1024 and _count(stage) == 0
    stage.add(receiver)
    with pytest.raises(StageError, match="1024 periodic"):
        bind(receiver, lambda event: None)
    with pytest.raises(StageError, match="1024 periodic"):
        receiver.clone()
    assert receiver._stage is stage and stage.clone_count == 0
    assert len(stage._timers) == 1024 and _count(stage) == 1


def test_periodic_registration_execution_overflow_is_atomic(stage: Stage) -> None:
    receiver = actor(stage)
    for _ in range(128):
        stage.wait(5)
    with pytest.raises(StageError, match="128-execution"):
        bind(receiver, lambda event: None)
    assert not stage._timers and _count(stage) == 128


def test_actual_ownership_matches_approved_record() -> None:
    from dataclasses import fields

    from plocks import Body
    from plocks._scripts import _Fiber, _Handler
    from plocks._timers import _Timer

    assert {f.name for f in fields(_Timer)} == {"handler", "seconds", "action"}
    assert "_timers" in Stage.__slots__
    assert all("_timers" not in cls.__slots__ for cls in (Sprite, Puppet, Body, Action))
    assert {f.name for f in fields(_Fiber)} == {"coroutine", "waiting", "children"}
    assert {f.name for f in fields(_Handler)} == {"start", "actor", "when_busy"}
