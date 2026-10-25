"""Input acquisition and composition; retained samples belong to Gamepad slots."""

from __future__ import annotations

from math import floor
from typing import TYPE_CHECKING

import pygame

from .errors import StageError
from .events import GamepadPress
from .gamepads import Gamepad, GamepadButton, GamepadInput, _button_index
from .geometry import _number

if TYPE_CHECKING:
    from ._scripts import _InputBinding
    from .stage import Stage


def _rebaseline(slot: Gamepad) -> None:
    stage = slot._stage
    stage._pending[:] = [
        event
        for event in stage._pending
        if not isinstance(event, GamepadPress) or event.gamepad is not slot
    ]
    for (owner, _), bindings in stage._gamepad_handlers.items():
        if owner is slot:
            for binding in bindings:
                binding.next_repeat = None


def _held(slot: Gamepad) -> frozenset[GamepadButton]:
    return frozenset(button for button in GamepadButton if slot.is_down(button))


def _transitions(
    slot: Gamepad, before: frozenset[GamepadButton], *, baseline: bool = False
) -> None:
    after = _held(slot)
    if not baseline:
        for button in GamepadButton:
            if button in after and button not in before:
                slot._stage._pending.append(GamepadPress(slot, button))
    for button in before - after:
        for binding in slot._stage._gamepad_handlers.get((slot, button), ()):
            binding.next_repeat = None


def _apply(slot: Gamepad, sample: GamepadInput, *, baseline: bool = False) -> None:
    sample.__post_init__()
    before = _held(slot)
    slot._buttons = frozenset(_button_index(button, slot.layout) for button in sample.buttons)
    slot._left, slot._right = sample.left_stick, sample.right_stick
    slot._triggers = sample.left_trigger, sample.right_trigger
    _transitions(slot, before, baseline=baseline)


def _clear_sample(slot: Gamepad) -> None:
    slot._buttons = frozenset()
    slot._left = slot._right = (0.0, 0.0)
    slot._triggers = (0.0, 0.0)


def _check_devices() -> None:
    from pygame._sdl2 import controller

    if controller.get_init():
        raise StageError("Another SDL controller session is already active")


def _open_devices(stage: Stage) -> None:
    from pygame._sdl2 import controller

    controller.init()
    _poll_devices(stage, baseline=True, refresh=True)


def _close_devices(stage: Stage) -> None:
    errors: list[BaseException] = []
    for slot in stage.gamepads:
        try:
            if slot._device is not None:
                slot._device.quit()
        except BaseException as error:  # noqa: BLE001 -- retire every owned slot before re-raising
            errors.append(error)
        finally:
            slot._device = None
            _clear_sample(slot)
            slot._key_buttons.clear()
            slot._left_keys = slot._right_keys = (None, None, None, None)
    if stage._target is not None:
        from pygame._sdl2 import controller

        try:
            controller.quit()
        except BaseException as error:  # noqa: BLE001 -- retain any earlier cleanup failure
            errors.append(error)
    if errors:
        raise errors[0]


def _axis(value: float) -> float:
    return max(-1.0, min(1.0, _number(value, "gamepad input")))


def _sample_native(slot: Gamepad) -> None:
    device = slot._device
    assert device is not None
    slot._buttons = frozenset(
        standard for native, standard in _native_buttons() if device.get_button(native)
    )
    values: list[float] = []
    for index in range(4):
        raw = device.get_axis(index)
        values.append(_axis(raw / (32768 if raw < 0 else 32767)))
    slot._left, slot._right = (values[0], -values[1]), (values[2], -values[3])
    slot._triggers = (
        max(0.0, _axis(device.get_axis(4) / 32767)),
        max(0.0, _axis(device.get_axis(5) / 32767)),
    )


def _native_refresh(stage: Stage) -> None:
    from pygame._sdl2 import controller

    if not controller.get_init():
        return
    for index in range(controller.get_count()):
        if not any(slot._device is None and slot not in stage._bots for slot in stage.gamepads):
            break
        if not controller.is_controller(index):
            continue
        device = controller.Controller(index)
        if any(slot._device is device for slot in stage.gamepads):
            continue
        slot = next(
            slot for slot in stage.gamepads if slot._device is None and slot not in stage._bots
        )
        slot._device = device
        _sample_native(slot)


def _poll_devices(stage: Stage, *, baseline: bool = False, refresh: bool = False) -> None:
    before = tuple(_held(slot) for slot in stage.gamepads)
    new_slots: set[Gamepad] = set()
    for slot in stage.gamepads:
        if slot._device is not None and not slot._device.attached():
            slot._device.quit()
            slot._device = None
            _clear_sample(slot)
            refresh = True
    if refresh:
        unassigned = {slot for slot in stage.gamepads if slot._device is None}
        _native_refresh(stage)
        new_slots = {slot for slot in unassigned if slot._device is not None}
    for slot in stage.gamepads:
        if slot._device is not None:
            _sample_native(slot)
    for slot, held in zip(stage.gamepads, before):
        if slot in stage._bots:
            continue
        _transitions(slot, held, baseline=baseline or slot in new_slots)


def _input_bindings(stage: Stage) -> tuple[_InputBinding, ...]:
    return tuple(binding for bindings in stage._gamepad_handlers.values() for binding in bindings)


def _clear_repeats(stage: Stage) -> None:
    for binding in _input_bindings(stage):
        binding.next_repeat = None


def _arm(stage: Stage, binding: _InputBinding, held: bool) -> None:
    binding.next_repeat = (
        stage.time + binding.repeat if held and binding.repeat is not None else None
    )


def _repeat(stage: Stage) -> None:
    from ._scripts import _trigger

    sources = [
        (GamepadPress(slot, button), tuple(bindings), slot.is_down(button))
        for (slot, button), bindings in stage._gamepad_handlers.items()
    ]
    for payload, bindings, held in sources:
        from ._ui import _menu_key

        if _menu_key(stage, payload.button):
            for binding in bindings:
                binding.next_repeat = None
            continue
        for binding in bindings:
            if not stage.running or stage.paused:
                return
            handler = binding.handler
            if not held or (handler.actor is not None and handler.actor._stage is not stage):
                binding.next_repeat = None
            deadline, interval = binding.next_repeat, binding.repeat
            if deadline is not None and interval is not None and deadline <= stage.time + 1e-12:
                binding.next_repeat = (
                    deadline + (floor(max(0, stage.time - deadline) / interval) + 1) * interval
                )
                if binding.next_repeat <= stage.time + 1e-12:
                    binding.next_repeat += interval
                _trigger(stage, handler, payload)


def _resume_repeats(stage: Stage) -> None:
    for (slot, button), bindings in stage._gamepad_handlers.items():
        for binding in bindings:
            if binding.handler.actor is None or binding.handler.actor._stage is stage:
                _arm(stage, binding, slot.is_down(button))


def _native_buttons() -> tuple[tuple[int, int], ...]:
    """Map SDL button constants to Plocks physical button positions."""
    return (
        (0, 0),
        (1, 1),
        (2, 2),
        (3, 3),
        (4, 8),
        (6, 9),
        (7, 10),
        (8, 11),
        (9, 4),
        (10, 5),
        (11, 12),
        (12, 13),
        (13, 14),
        (14, 15),
    )


def _native_button_event(stage: Stage, event: pygame.event.Event) -> None:
    """Preserve queued press/release edges even when final polling sees released.

    SDL event instance IDs differ from shifting device indexes. Resolve them
    locally against the current device list, then borrow the owned Controller.
    No instance-ID copy or device index is retained on the logical player slot.
    """
    from pygame._sdl2 import controller

    if not controller.get_init():
        return
    standard = dict(_native_buttons()).get(int(event.button))
    if standard is None:
        return
    for index in range(controller.get_count()):
        if not controller.is_controller(index):
            continue
        joystick = pygame.joystick.Joystick(index)
        if joystick.get_instance_id() != event.instance_id:
            continue
        device = controller.Controller(index)
        slot = next((slot for slot in stage.gamepads if slot._device is device), None)
        if slot is not None:
            before = _held(slot)
            slot._buttons = (
                slot._buttons | {standard}
                if event.type == pygame.CONTROLLERBUTTONDOWN
                else slot._buttons - {standard}
            )
            _transitions(slot, before)
        return
