"""Logical input composition, bounded repeat clocks, stable slots and cleanup."""

from collections.abc import Iterator
from pathlib import Path

import pygame
import pytest

from plocks import (
    Event,
    GamepadDown,
    GamepadLayout,
    GamepadPress,
    Key,
    Sprite,
    Stage,
    StageError,
    WhenBusy,
    _gamepads,
)
from plocks import GamepadButton as Button
from plocks._runtime import _clear_input, _key, advance, close, dispatch
from plocks.conditions import _test

IMAGE = Path(__file__).parent / "fixtures/games/integrations_proof/assets/hero.png"


@pytest.fixture
def world() -> Iterator[tuple[Stage, Sprite]]:
    stage = Stage()
    actor = Sprite(IMAGE)
    stage.add(actor)
    stage._state, stage._last_wall = "running", 0.0
    yield stage, actor
    close(stage)


def key(stage: Stage, value: Key, held: bool = True) -> None:
    _key(
        stage,
        pygame.event.Event(
            pygame.KEYDOWN if held else pygame.KEYUP,
            key=getattr(
                pygame, "K_" + (value.value if len(value.value) == 1 else value.value.upper())
            ),
        ),
    )
    dispatch(stage)


def ticks(stage: Stage, count: int) -> None:
    for _ in range(count):
        advance(stage, (stage._last_wall or 0.0) + 1 / stage.tick_rate)


def test_slots_validation_and_read_only_membership() -> None:
    stage = Stage(gamepad_count=6, gamepad_layout=GamepadLayout.NINTENDO)
    assert len(stage.gamepads) == 6 and stage.gamepads[4].index == 4
    assert all(
        p.layout is GamepadLayout.NINTENDO and not p.connected and p.name is None
        for p in stage.gamepads
    )
    for count in (0, 17, -1):
        with pytest.raises(ValueError):
            Stage(gamepad_count=count)
    with pytest.raises(TypeError):
        Stage(gamepad_count=True)
    with pytest.raises(AttributeError):
        stage.gamepads = ()  # type: ignore[misc]


def test_keyboard_and_physical_or_preserve_one_press(world: tuple[Stage, Sprite]) -> None:
    stage, actor = world
    pad = stage.gamepads[0]
    pad.map_key(Key.SPACE, Button.A)
    pad.map_key(Key.ENTER, Button.A)
    events: list[GamepadPress] = []

    @actor.on_gamepad_button_down(Button.A, gamepad=pad)
    def receive(event: Event[Sprite, GamepadPress]) -> None:
        assert event.source is stage and event.target is actor
        events.append(event.data)

    key(stage, Key.SPACE)
    before = _gamepads._held(pad)
    pad._buttons = frozenset({0})
    _gamepads._transitions(pad, before)
    key(stage, Key.ENTER)
    key(stage, Key.SPACE, False)
    key(stage, Key.ENTER, False)
    assert pad.is_down(Button.A) and len(events) == 1
    before = _gamepads._held(pad)
    pad._buttons = frozenset()
    _gamepads._transitions(pad, before)
    key(stage, Key.SPACE)
    assert len(events) == 2 and events[0].gamepad is pad and events[0].button is Button.A


def test_layout_rebaseline_does_not_invent_events(world: tuple[Stage, Sprite]) -> None:
    stage, _ = world
    pad = stage.gamepads[0]
    pad._buttons = frozenset({0})
    assert pad.is_down(Button.A) and not pad.is_down(Button.B)
    pad.layout = GamepadLayout.NINTENDO
    assert pad.is_down(Button.B) and not pad.is_down(Button.A)
    pad.map_key(Key.SPACE, Button.A)
    _key(stage, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    assert any(isinstance(e, GamepadPress) for e in stage._pending)
    pad.layout = GamepadLayout.XBOX
    assert not any(isinstance(e, GamepadPress) for e in stage._pending)
    assert pad.is_down(Button.A)


def test_radial_dead_zone_and_keyboard_override(world: tuple[Stage, Sprite]) -> None:
    stage, _ = world
    pad = stage.gamepads[0]
    pad._left = (0.1, 0)
    assert pad.left_stick == (0, 0)
    pad._left = (0.6, 0.8)
    assert pad.left_stick == pytest.approx((0.6, 0.8))
    pad.map_left_stick(left=Key.A, right=Key.D, up=Key.W, down=Key.S)
    key(stage, Key.W)
    assert pad.left_stick == (0, 1)
    key(stage, Key.D)
    assert pad.left_stick == pytest.approx((2**-0.5, 2**-0.5))
    key(stage, Key.A)
    key(stage, Key.S)
    assert pad.left_stick == (0, 0)
    pad.map_left_stick()
    assert pad.left_stick == pytest.approx((0.6, 0.8))
    for invalid in (-1, 1, float("inf"), float("nan")):
        with pytest.raises(ValueError):
            pad.dead_zone = invalid


def test_turbo_uses_simulation_time_and_key_repeat_is_optional(world: tuple[Stage, Sprite]) -> None:
    stage, _ = world
    pad = stage.gamepads[0]
    pad.map_key(Key.F, Button.B)
    times: list[float] = []
    plain: list[Key] = []
    stage.on_gamepad_button_down(Button.B, gamepad=pad, repeat=0.1)(
        lambda event: times.append(stage.time)
    )
    stage.on_key_down(Key.F)(lambda event: plain.append(event.data))
    key(stage, Key.F)
    ticks(stage, 20)
    assert times == pytest.approx([0, 0.1, 0.2, 0.3]) and plain == [Key.F]
    key(stage, Key.F, False)
    ticks(stage, 20)
    assert len(times) == 4
    repeated: list[float] = []
    stage.on_key_down(Key.G, repeat=0.05)(lambda event: repeated.append(stage.time))
    key(stage, Key.G)
    ticks(stage, 7)
    assert len(repeated) == 3


def test_turbo_pause_catchup_limit_and_removal(world: tuple[Stage, Sprite]) -> None:
    stage, actor = world
    calls: list[float] = []
    actor.on_key_down(Key.F, repeat=0.001)(lambda event: calls.append(stage.time))
    key(stage, Key.F)
    advance(stage, 10)
    assert len(calls) <= 6
    stage.pause()
    frozen = stage.time
    ticks(stage, 10)
    assert stage.time == frozen
    count = len(calls)
    stage.resume()
    ticks(stage, 2)
    assert len(calls) <= count + 1
    stage.remove(actor)
    stage.add(actor)
    ticks(stage, 5)
    assert len(calls) <= count + 1
    key(stage, Key.F, False)
    key(stage, Key.F)
    assert len(calls) == count + 2


def test_busy_ignore_and_restart_remain_registration_owned(world: tuple[Stage, Sprite]) -> None:
    stage, actor = world
    actor.on_key_down(Key.F, actor.sequence().wait(0.5).move(10), repeat=0.05)
    key(stage, Key.F)
    ticks(stage, 20)
    assert len(stage._actions) == 1 and actor.x == 0
    key(stage, Key.F, False)
    ticks(stage, 20)
    assert actor.x == 10
    actor.on_key_down(
        Key.G, actor.sequence().wait(0.2).move(20), repeat=0.05, when_busy=WhenBusy.RESTART
    )
    key(stage, Key.G)
    ticks(stage, 25)
    assert actor.x == 10 and len(stage._actions) == 1
    key(stage, Key.G, False)
    ticks(stage, 20)
    assert actor.x == 30


def test_wildcard_and_filtered_slots_have_independent_repeat_clocks(
    world: tuple[Stage, Sprite],
) -> None:
    stage, _ = world
    one, two = stage.gamepads[:2]
    one.map_key(Key.A, Button.A)
    two.map_key(Key.B, Button.A)
    all_presses: list[int] = []
    filtered: list[int] = []
    stage.on_gamepad_button_down(Button.A, repeat=0.1)(
        lambda e: all_presses.append(e.data.gamepad.index)
    )
    stage.on_gamepad_button_down(Button.A, gamepad=two)(
        lambda e: filtered.append(e.data.gamepad.index)
    )
    key(stage, Key.A)
    ticks(stage, 3)
    key(stage, Key.B)
    ticks(stage, 8)
    assert all_presses == [0, 1, 0, 1] and filtered == [1]


def test_configuration_validation_is_atomic_and_cross_stage_rejected(
    world: tuple[Stage, Sprite],
) -> None:
    stage, actor = world
    pad = stage.gamepads[0]
    pad.map_key(Key.A, Button.A)
    for invalid in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            actor.on_gamepad_button_down(Button.A, repeat=invalid)
        with pytest.raises(ValueError):
            stage.on_key_down(Key.SPACE, repeat=invalid)
    with pytest.raises(TypeError):
        stage.on_key_down(Key.SPACE, repeat=True)
    with pytest.raises(StageError):
        actor.on_gamepad_button_down(Button.A, gamepad=Stage().gamepads[0])
    condition = GamepadDown(Button.A, pad)
    key(stage, Key.A)
    assert _test(condition, actor)
    with pytest.raises(StageError):
        _test(GamepadDown(Button.A, Stage().gamepads[0]), actor)


def test_clear_and_close_retire_all_input(world: tuple[Stage, Sprite]) -> None:
    stage, _ = world
    pad = stage.gamepads[0]
    pad.map_key(Key.A, Button.A)
    key(stage, Key.A)
    stage.on_key_down(Key.A, repeat=0.1)(lambda event: None)
    _clear_input(stage)
    assert not pad.is_down(Button.A) and pad.left_stick == (0, 0)
    close(stage)
    assert not pad.connected and pad.name is None and not stage._gamepad_handlers
    assert not stage._keys and not stage._pending
    with pytest.raises(StageError):
        pad.map_key(Key.A, Button.B)
    close(stage)


def test_puppet_events_and_registration_snapshots(world: tuple[Stage, Sprite]) -> None:
    from plocks import Puppet

    stage, _ = world
    person = Puppet.stick_figure()
    stage.add(person)
    slot = stage.gamepads[0]
    slot.map_key(Key.A, Button.A)
    calls: list[str] = []

    @person.on_gamepad_button_down(Button.A, gamepad=slot)
    def first(event: Event[Puppet, GamepadPress]) -> None:
        assert event.target is person and event.source is stage
        calls.append("first")
        person.on_gamepad_button_down(Button.A, gamepad=slot)(lambda e: calls.append("later"))

    key(stage, Key.A)
    assert calls == ["first"]
    key(stage, Key.A, False)
    key(stage, Key.A)
    assert calls == ["first", "first", "later"]


def test_automatic_suspension_clears_then_rearms_without_press(
    world: tuple[Stage, Sprite], monkeypatch: pytest.MonkeyPatch
) -> None:
    from plocks._runtime import poll

    stage, _ = world
    stage.on_key_down(Key.F, repeat=0.1)(lambda e: None)
    key(stage, Key.F)
    with monkeypatch.context() as patch:
        patch.setattr(pygame.event, "get", lambda: [pygame.event.Event(pygame.WINDOWFOCUSLOST)])
        poll(stage)
        assert stage.paused and not stage.keyboard.is_down(Key.F)
        assert stage._keys[Key.F][0].next_repeat is None
        patch.setattr(pygame.event, "get", lambda: [pygame.event.Event(pygame.WINDOWFOCUSGAINED)])
        patch.setattr(_gamepads, "_poll_devices", lambda *a, **kw: None)
        poll(stage)
        assert not stage.paused and not stage._pending


@pytest.mark.parametrize("failure", ["startup", "callback"])
def test_native_acquisition_and_callback_failures_release_resources(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    from pygame._sdl2 import controller

    stage = Stage()
    actor = Sprite(IMAGE)
    stage.add(actor)
    actor.on_gamepad_button_down(Button.A, actor.sequence().wait(1))
    if failure == "startup":
        original = _gamepads._open_devices

        def fail(stage: Stage) -> None:
            original(stage)
            raise LookupError("input acquisition failed")

        monkeypatch.setattr(_gamepads, "_open_devices", fail)
    else:

        @stage.on_start
        def fail_callback(event: Event[Stage, None]) -> None:
            raise LookupError("input callback failed")

    with pytest.raises(LookupError, match="input"):
        stage.run()
    assert stage._state == "closed" and stage._target is None and not stage.objects
    assert not controller.get_init() and not stage._actions and not stage._gamepad_handlers
    assert all(slot._device is None and not slot._buttons for slot in stage.gamepads)
    assert actor._stage is None


@pytest.mark.parametrize("already_suspended", [False, True])
def test_controller_edges_during_focus_resume_are_rebaselined(
    world: tuple[Stage, Sprite], monkeypatch: pytest.MonkeyPatch, already_suspended: bool
) -> None:
    from plocks._runtime import poll

    stage, _ = world
    if already_suspended:
        stage._set_pause("focus", True)
    events = [] if already_suspended else [pygame.event.Event(pygame.WINDOWFOCUSLOST)]
    events.extend(
        [
            pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, button=0, instance_id=1),
            pygame.event.Event(pygame.WINDOWFOCUSGAINED),
        ]
    )
    sampled: list[bool] = []

    def sample(stage: Stage, *, baseline: bool, refresh: bool) -> None:
        sampled.append(baseline)

    def unexpected(stage: Stage, event: pygame.event.Event) -> None:
        raise AssertionError("Suspended controller edge must not be delivered")

    monkeypatch.setattr(pygame.event, "get", lambda: events)
    monkeypatch.setattr(_gamepads, "_poll_devices", sample)
    monkeypatch.setattr(_gamepads, "_native_button_event", unexpected)
    poll(stage)
    assert sampled == [True] and not stage._pending and not stage.paused


@pytest.mark.parametrize("layout", list(GamepadLayout))
def test_default_keyboard_controls_are_independent_under_both_layouts(
    world: tuple[Stage, Sprite], layout: GamepadLayout
) -> None:
    stage, _ = world
    one, two, third, _ = stage.gamepads
    one.layout = two.layout = layout
    calls: list[tuple[int, Button]] = []
    for button in (Button.A, Button.B):
        stage.on_gamepad_button_down(button)(
            lambda e: calls.append((e.data.gamepad.index, e.data.button))
        )
    key(stage, Key.SPACE)
    assert one.is_down(Button.A) and not two.is_down(Button.A)
    key(stage, Key.ENTER)
    key(stage, Key.F)
    _key(stage, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RSHIFT))
    dispatch(stage)
    assert calls == [(0, Button.A), (1, Button.A), (0, Button.B), (1, Button.B)]
    assert not third.is_down(Button.A) and not third.is_down(Button.B)
    for slot, directions in (
        (one, (Key.A, Key.D, Key.W, Key.S)),
        (two, (Key.LEFT, Key.RIGHT, Key.UP, Key.DOWN)),
    ):
        for direction, button, vector in zip(
            directions,
            (Button.LEFT, Button.RIGHT, Button.UP, Button.DOWN),
            ((-1, 0), (1, 0), (0, 1), (0, -1)),
        ):
            key(stage, direction)
            assert slot.left_stick == vector and slot.is_down(button)
            assert third.left_stick == (0, 0) and not third.is_down(button)
            key(stage, direction, False)
    assert not one.connected and not two.connected


def test_default_mappings_can_be_cleared_or_overridden(world: tuple[Stage, Sprite]) -> None:
    stage, _ = world
    one, two = stage.gamepads[:2]
    one.clear_keyboard()
    key(stage, Key.SPACE)
    key(stage, Key.W)
    assert not one.is_down(Button.A) and not one.is_down(Button.UP)
    assert one.left_stick == (0, 0)
    key(stage, Key.ENTER)
    assert two.is_down(Button.A)
    two.map_key(Key.ENTER, None)
    assert not two.is_down(Button.A)
    one.map_key(Key.H, Button.A)
    key(stage, Key.H)
    assert one.is_down(Button.A)
    assert stage.keyboard.is_down(Key.H)


def test_native_hotplug_keeps_slots_and_limits_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Native polling fills six slots, ignores excess devices and reuses only a detached slot."""
    from unittest.mock import MagicMock

    from pygame._sdl2 import controller

    stage = Stage(gamepad_count=6)
    stage._state = "running"
    devices = [MagicMock(spec=controller.Controller) for _ in range(7)]
    for index, device in enumerate(devices):
        device.attached.return_value = True
        device.get_button.return_value = False
        device.get_axis.return_value = 0
        device.name = f"Test {index}"
    connected = list(range(7))
    monkeypatch.setattr(controller, "get_init", lambda: True)
    monkeypatch.setattr(controller, "get_count", lambda: len(connected))
    monkeypatch.setattr(controller, "is_controller", lambda index: True)
    monkeypatch.setattr(controller, "Controller", lambda index: devices[connected[index]])
    try:
        _gamepads._poll_devices(stage, refresh=True)
        assert [pad._device for pad in stage.gamepads] == devices[:6]
        assert stage.gamepads[0].connected and stage.gamepads[0].name == "Test 0"
        key(stage, Key.SPACE)
        assert stage.gamepads[0].is_down(Button.A)
        devices[0].attached.return_value = False
        connected.remove(0)
        _gamepads._poll_devices(stage)
        assert [pad._device for pad in stage.gamepads] == [devices[6], *devices[1:6]]
        assert stage.gamepads[0].is_down(Button.A) and not stage._pending
        devices[0].quit.assert_called_once()
    finally:
        close(stage)
    assert all(pad._device is None for pad in stage.gamepads)
