"""Reusable definition snapshots and synchronous, typed event execution."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from plocks import (
    Event,
    GamepadButton,
    GamepadDown,
    GamepadPress,
    Key,
    Message,
    Script,
    Sprite,
    Stage,
)
from plocks._runtime import advance, close, dispatch


@pytest.fixture
def world() -> Iterator[tuple[Stage, Sprite, Sprite]]:
    stage = Stage()
    stage.gamepads[0].map_key(Key.A, GamepadButton.LEFT)
    stage.gamepads[0].map_key(Key.H, GamepadButton.Y)
    stage.gamepads[0].map_key(Key.LEFT, GamepadButton.LEFT)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    stage.gamepads[0].map_key(Key.UP, GamepadButton.UP)
    stage.gamepads[0].map_key(Key.Z, GamepadButton.R)
    # Existing ready-made pixels keep the integration path independent of artwork generation.
    image = Path(__file__).parents[1] / "src/plocks/_games/platformer/assets/hero.png"
    first, second = Sprite(image), Sprite(image, x=100)
    stage.add(first)
    stage.add(second)
    stage._state = "running"
    stage._last_wall = 0.0
    yield stage, first, second
    close(stage)


def ticks(stage: Stage, count: int) -> None:
    for _ in range(count):
        advance(stage, (stage._last_wall or 0.0) + 1 / stage.tick_rate)


def test_shared_script_branch_event_and_independent_completion(
    world: tuple[Stage, Sprite, Sprite],
) -> None:
    stage, first, second = world
    finished = Message[None]("finished")
    received: list[Sprite] = []

    @stage.on_broadcast(finished)
    def report(event: Event[Stage, None]) -> None:
        assert isinstance(event.source, Sprite)
        received.append(event.source)

    trip = (
        Script()
        .when(
            GamepadDown(GamepadButton.UP, gamepad=stage.gamepads[0]),
            then=Script().glide_by(y=60, seconds=0.2),
            either=Script().glide_by(y=-60, seconds=0.2),
        )
        .broadcast(finished)
    )
    stage._held_keys.add(Key.UP)
    one = first.act(trip)
    two = second.act(trip)
    ticks(stage, 20)
    assert one.done and two.done
    assert first.y == second.y == 60
    assert received == [first, second]
    assert first.x == 0 and second.x == 100


def test_snapshot_pause_cancel_and_detach(world: tuple[Stage, Sprite, Sprite]) -> None:
    stage, first, second = world
    trip = Script().glide_by(x=60, seconds=1)
    one = first.act(trip)
    two = second.act(trip)
    trip.glide_by(x=500, seconds=1)
    ticks(stage, 15)
    stage.pause()
    position = second.position
    ticks(stage, 15)
    assert second.position == position
    stage.resume()
    ticks(stage, 1)
    one.cancel()
    frozen = first.position
    ticks(stage, 65)
    assert first.position == frozen and one.cancelled
    assert second.x == 160 and two.done
    next_action = second.act(trip)
    ticks(stage, 3)
    stage.remove(second)
    assert next_action.cancelled
    stage.add(second)
    ticks(stage, 3)
    assert not stage._actions


def test_callback_selects_script_and_busy_does_not_execute_twice(
    world: tuple[Stage, Sprite, Sprite],
) -> None:
    stage, first, _ = world
    calls = []

    @first.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])
    def start(event: Event[Sprite, GamepadPress]) -> Script[Sprite]:
        calls.append(event.data)
        return Script(Sprite).glide_by(y=20, seconds=0.1)

    stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.A))
    dispatch(stage)
    stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.A))
    dispatch(stage)
    ticks(stage, 15)
    assert calls == [GamepadPress(stage.gamepads[0], GamepadButton.A)] and first.y == 20


def test_async_registration_and_return_rejected(world: tuple[Stage, Sprite, Sprite]) -> None:
    stage, first, _ = world

    async def unsupported(event: Event[Stage, GamepadPress]) -> None:
        pass

    with pytest.raises(TypeError, match="synchronous"):
        stage.on_button_down(GamepadButton.R, gamepad=stage.gamepads[0])(unsupported)  # type: ignore[type-var]

    @stage.on_button_down(GamepadButton.LEFT, gamepad=stage.gamepads[0])
    def bad(event: Event[Stage, GamepadPress]) -> None:
        return unsupported(event)  # type: ignore[return-value]

    stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.LEFT))
    with pytest.raises(TypeError, match="callbacks must return"):
        dispatch(stage)
    assert not hasattr(first.wait(0), "__await__")


def test_nested_snapshot_and_repeated_branch_selection(world: tuple[Stage, Sprite, Sprite]) -> None:
    stage, first, _ = world
    child = Script().move(2)
    recipe = (
        Script()
        .repeat(2)
        .call(child)
        .when(
            GamepadDown(GamepadButton.LEFT, gamepad=stage.gamepads[0]),
            then=Script().move(10),
            either=Script().move(-1),
        )
        .wait(0.05)
    )
    child.move(100)
    action = first.act(recipe)
    ticks(stage, 2)
    stage._held_keys.add(Key.LEFT)
    ticks(stage, 15)
    assert action.done and first.x == 13


def test_false_without_either_and_touching_reference_lifetime(
    world: tuple[Stage, Sprite, Sprite],
) -> None:
    from plocks import Not, Touching

    stage, first, second = world
    stage.remove(second)
    first.act(
        Script()
        .when(Touching(second), then=Script().move(100))
        .when(Not(Touching(second)), then=Script().move(3))
    )
    ticks(stage, 2)
    assert first.x == 3
    other = Stage()
    other.gamepads[0].map_key(Key.A, GamepadButton.LEFT)
    other.gamepads[0].map_key(Key.H, GamepadButton.Y)
    other.gamepads[0].map_key(Key.LEFT, GamepadButton.LEFT)
    other.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    other.gamepads[0].map_key(Key.UP, GamepadButton.UP)
    other.gamepads[0].map_key(Key.Z, GamepadButton.R)
    other.add(second)
    try:
        first.act(Script().when(Touching(second), then=Script().move(1)))
        with pytest.raises(Exception, match="another stage"):
            ticks(stage, 1)
    finally:
        close(other)


def test_targeted_events_separate_source_and_receiver_and_preserve_payload_identity(
    world: tuple[Stage, Sprite, Sprite],
) -> None:
    stage, first, second = world
    channel = Message[list[int]]("data")
    equal_name = Message[list[int]]("data")
    data = [1]
    seen: list[tuple[object, object, object]] = []

    @stage.on_broadcast(channel)
    def global_observer(event: Event[Stage, list[int]]) -> None:
        seen.append(("global", event.source, event.data))

    @second.on_broadcast(channel)
    def receiver(event: Event[Sprite, list[int]]) -> None:
        actor = event.target
        seen.append((actor, event.source, event.data))

    @second.on_broadcast(equal_name)
    def wrong(event: Event[Sprite, list[int]]) -> None:
        pytest.fail("Equal diagnostic names are not channel identities")

    sending = first.broadcast(channel, data, to=second, wait=True)
    data.append(2)
    ticks(stage, 5)
    assert sending.done and len(seen) == 1
    assert seen[0][0] is second and seen[0][1] is first and seen[0][2] is data
    assert data == [1, 2]


def test_delivery_batches_are_fifo_and_emit_never_recurses(
    world: tuple[Stage, Sprite, Sprite],
) -> None:
    stage, _, _ = world
    channel = Message[int]("fifo")
    seen: list[int] = []

    @stage.on_broadcast(channel)
    def receiver(event: Event[Stage, int]) -> None:
        seen.append(event.data)
        if event.data == 1:
            stage.broadcast(channel, 3)

    stage.broadcast(channel, 1)
    stage.broadcast(channel, 2)
    ticks(stage, 1)
    assert not seen
    ticks(stage, 1)
    assert seen == [1, 2]
    ticks(stage, 2)
    assert seen == [1, 2, 3]


@pytest.mark.parametrize("remove_source", [True, False])
def test_undelivered_event_removed_without_resurrection(
    world: tuple[Stage, Sprite, Sprite], remove_source: bool
) -> None:
    from plocks._scripts import _step

    stage, first, second = world
    channel = Message[None]("removed")
    seen: list[object] = []

    @second.on_broadcast(channel)
    def receiver(event: Event[Sprite, None]) -> None:
        actor = event.target
        seen.append(actor)

    send = first.broadcast(channel, to=second, wait=True)
    _step(stage)
    assert len(stage._messages) == 1
    removed = first if remove_source else second
    stage.remove(removed)
    stage.add(removed)
    ticks(stage, 5)
    assert not seen and send.done and not stage._messages


def test_sender_cancellation_keeps_accepted_receiver_alive(
    world: tuple[Stage, Sprite, Sprite],
) -> None:
    stage, first, second = world
    channel = Message[None]("work")
    second.on_broadcast(channel, Script().glide_by(x=30, seconds=0.2))
    send = first.broadcast(channel, wait=True)
    ticks(stage, 4)
    stage.remove(first)
    ticks(stage, 20)
    assert send.cancelled and second.x == 130


def test_restart_joins_only_original_invocation(world: tuple[Stage, Sprite, Sprite]) -> None:
    from plocks import WhenBusy

    stage, _, second = world
    channel = Message[None]("restart")
    second.on_broadcast(channel, Script().wait(1), when_busy=WhenBusy.RESTART)
    first = stage.broadcast(channel, wait=True)
    ticks(stage, 3)
    replacement = stage.broadcast(channel, wait=True)
    ticks(stage, 3)
    assert first.done and not replacement.done
    ticks(stage, 65)
    assert replacement.done


def test_callback_returned_script_scopes_other_new_actions(
    world: tuple[Stage, Sprite, Sprite],
) -> None:
    stage, first, _ = world

    @first.on_button_down(GamepadButton.LEFT, gamepad=stage.gamepads[0])
    def launch(event: Event[Sprite, GamepadPress]) -> Script[Sprite]:
        actor = event.target
        actor.glide_by(x=500, seconds=10)
        return Script(Sprite).wait(0.1)

    stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.LEFT))
    dispatch(stage)
    ticks(stage, 10)
    frozen = first.x
    assert 0 < frozen < 20 and not stage._actions
    ticks(stage, 20)
    assert first.x == frozen


def test_empty_delivery_join_and_queue_bound(world: tuple[Stage, Sprite, Sprite]) -> None:
    from plocks import StageError

    stage, _, _ = world
    send = stage.broadcast(Message[None]("nobody"), wait=True)
    ticks(stage, 3)
    assert send.done
    channel = Message[object]("bounded")

    for _ in range(256):
        stage._enqueue(channel, stage, None, None)
    with pytest.raises(StageError, match="256-delivery"):
        stage._enqueue(channel, stage, None, None)


def test_async_callable_and_wrapped_coroutine_are_rejected(
    world: tuple[Stage, Sprite, Sprite],
) -> None:
    from collections.abc import Callable
    from functools import wraps
    from typing import cast

    stage, _, _ = world

    async def asynchronous(event: Event[Stage, GamepadPress]) -> None:
        pass

    @wraps(asynchronous)
    def wrapped(event: Event[Stage, GamepadPress]) -> object:
        return asynchronous(event)

    class AsyncCallable:
        async def __call__(self, event: Event[Stage, GamepadPress]) -> None:
            pass

    for callback in (wrapped, AsyncCallable()):
        with pytest.raises(TypeError, match="synchronous"):
            stage.on_button_down(GamepadButton.LEFT, gamepad=stage.gamepads[0])(
                cast(Callable[[Event[Stage, GamepadPress]], None], callback)
            )
    assert not stage._gamepad_handlers


def test_puppet_capability_and_skeleton_admission(world: tuple[Stage, Sprite, Sprite]) -> None:
    from typing import cast

    from plocks import Puppet

    stage, first, _ = world
    person = Puppet.stick_figure()
    other = Puppet.stick_figure()
    stage.add(person)
    shared = Script().glide_by(x=20, seconds=0.1)
    first.act(shared)
    person.act(shared)
    ticks(stage, 10)
    assert first.x == person.x == 20
    with pytest.raises(TypeError, match="incompatible"):
        person.act(cast(Script[Puppet], Script(Sprite).set_costume(first.costume)))
    with pytest.raises(ValueError, match="another skeleton"):
        person.act(Script(Puppet).poses((other.pose,), fps=2))


def test_callback_cannot_leave_work_on_detached_receiver(
    world: tuple[Stage, Sprite, Sprite],
) -> None:
    from plocks import StageError

    stage, first, _ = world

    @first.on_button_down(GamepadButton.LEFT, gamepad=stage.gamepads[0])
    def remove_self(event: Event[Sprite, GamepadPress]) -> Script[Sprite]:
        actor = event.target
        stage.remove(actor)
        return Script(Sprite).wait(1)

    stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.LEFT))
    with pytest.raises(StageError, match="detached during"):
        dispatch(stage)
    assert not stage._actions


def test_broadcast_has_independent_immutable_receiver_envelopes(
    world: tuple[Stage, Sprite, Sprite],
) -> None:
    from dataclasses import FrozenInstanceError

    import plocks
    from plocks import Actor, Puppet

    assert not hasattr(plocks, "MessageData")
    stage, first, second = world
    person = Puppet.stick_figure()
    stage.add(person)
    channel = Message[list[int]]("shared payload")
    payload = [1]
    deliveries: list[Event[Stage | Actor, list[int]]] = []

    def receive(message: Event[Stage | Actor, list[int]]) -> None:
        deliveries.append(message)

    stage.on_broadcast(channel)(receive)
    first.on_broadcast(channel)(receive)
    second.on_broadcast(channel)(receive)
    person.on_broadcast(channel)(receive)
    first.broadcast(channel, payload, wait=True)
    ticks(stage, 5)
    assert [message.target for message in deliveries] == [stage, first, second, person]
    assert len({id(message) for message in deliveries}) == 4
    assert all(isinstance(message, Event) and message.source is first for message in deliveries)
    assert all(message.data is payload for message in deliveries)
    payload.append(2)
    assert deliveries[0].data == [1, 2]
    with pytest.raises(FrozenInstanceError):
        setattr(deliveries[0], "target", second)  # noqa: B010 -- exercise frozen runtime validation from untyped code
    assert deliveries[0].target is stage


def test_engine_events_have_receiver_target_and_stage_source(
    world: tuple[Stage, Sprite, Sprite],
) -> None:
    from plocks import Event

    stage, first, _ = world
    keys: list[Event[Stage | Sprite, GamepadPress]] = []
    updates: list[Event[Stage | Sprite, float]] = []

    def pressed(event: Event[Stage | Sprite, GamepadPress]) -> None:
        keys.append(event)

    def updated(event: Event[Stage | Sprite, float]) -> None:
        updates.append(event)

    stage.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])(pressed)
    first.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])(pressed)
    stage.on_update(updated)
    first.on_update(updated)
    stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.A))
    ticks(stage, 1)
    assert [event.target for event in keys] == [stage, first]
    assert all(event.source is stage and event.data.button is GamepadButton.A for event in keys)
    assert [event.target for event in updates] == [stage, first]
    assert all(event.source is stage and event.data == 1 / stage.tick_rate for event in updates)
    assert not hasattr(keys[0], "message") and not hasattr(keys[0], "event")


def test_message_apis_reject_engine_occurrences(world: tuple[Stage, Sprite, Sprite]) -> None:
    from typing import cast

    from plocks import Event

    stage, first, _ = world
    occurrence = Event(stage, first, None)
    with pytest.raises(TypeError, match="Message token"):
        first.broadcast(cast(Message[None], occurrence))
    with pytest.raises(TypeError, match="Message token"):
        stage.on_broadcast(cast(Message[None], occurrence))
    assert not stage._message_handlers and not stage._messages


def test_one_callback_handles_keys_and_broadcasts_for_every_receiver(
    world: tuple[Stage, Sprite, Sprite],
) -> None:
    from plocks import Actor, Puppet

    stage, first, second = world
    person = Puppet.stick_figure()
    stage.add(person)
    channel = Message[GamepadPress]("button command")
    seen: list[Event[Stage | Actor, GamepadPress]] = []

    def receive(event: Event[Stage | Actor, GamepadPress]) -> None:
        seen.append(event)

    stage.on_button_down(GamepadButton.Y, gamepad=stage.gamepads[0])(receive)
    stage.on_broadcast(channel)(receive)
    for actor in (first, person):
        actor.on_button_down(GamepadButton.Y, gamepad=stage.gamepads[0])(receive)
        actor.on_broadcast(channel)(receive)
    stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.Y))
    dispatch(stage)
    second.broadcast(channel, GamepadPress(stage.gamepads[0], GamepadButton.Y))
    ticks(stage, 3)

    assert [event.target for event in seen] == [stage, first, person] * 2
    assert all(type(event) is Event and event.data.button is GamepadButton.Y for event in seen)
    assert all(event.source is stage for event in seen[:3])
    assert all(event.source is second for event in seen[3:])
    assert all(not hasattr(event, "message") for event in seen)
