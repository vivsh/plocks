"""Stable player controls combining a physical gamepad and optional keyboard keys."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot
from typing import TYPE_CHECKING

from .errors import StageError
from .geometry import Point, _number
from .input import Key

if TYPE_CHECKING:
    from pygame._sdl2.controller import Controller

    from .stage import Stage

type _StickKeys = tuple[Key | None, Key | None, Key | None, Key | None]


class GamepadLayout(Enum):
    """Choose the face-button labels taught by your game; no hardware guessing."""

    XBOX = "xbox"
    NINTENDO = "nintendo"


class GamepadButton(Enum):
    """Logical gamepad buttons; A/B/X/Y follow the slot's selected layout."""

    A = "a"
    B = "b"
    X = "x"
    Y = "y"
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    L = "l"
    R = "r"
    LEFT_STICK = "left_stick"
    RIGHT_STICK = "right_stick"
    START = "start"
    SELECT = "select"


@dataclass(frozen=True, slots=True)
class GamepadInput:
    """An immutable logical input sample for automated and remote players.

    Sticks use x right/y up with length at most one; triggers are in 0..1.
    Invalid values raise before any existing held controls are changed.
    """

    buttons: frozenset[GamepadButton] = frozenset()
    left_stick: Point = (0.0, 0.0)
    right_stick: Point = (0.0, 0.0)
    left_trigger: float = 0.0
    right_trigger: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.buttons, frozenset) or any(
            not isinstance(button, GamepadButton) for button in self.buttons
        ):
            raise TypeError("buttons must be a frozenset of GamepadButton values")
        for name, stick in (("left_stick", self.left_stick), ("right_stick", self.right_stick)):
            if not isinstance(stick, tuple) or len(stick) != 2:
                raise TypeError(f"{name} must be an (x, y) tuple")
            x, y = (_number(value, name) for value in stick)
            if hypot(x, y) > 1 + 1e-12:
                raise ValueError(f"{name} length must be at most one")
        for value in (self.left_trigger, self.right_trigger):
            if not 0 <= _number(value, "trigger") <= 1:
                raise ValueError("Trigger pressure must be in 0..1")


class Gamepad:
    """One stable player slot, obtained from stage.gamepads (zero-based).

    The first two slots start with keyboard controls (WASD/Space/F and
    arrows/Enter/Right Shift). Later slots start unbound. Buttons combine all contributors;
    mapped direction keys take over their stick while any direction is held.
    Local slots combine keyboard and hardware. Remote/automated slots use their
    exclusive logical source; device metadata remains about physical hardware.
    """

    __slots__ = (
        "_buttons",
        "_dead_zone",
        "_device",
        "_key_buttons",
        "_layout",
        "_left",
        "_left_keys",
        "_right",
        "_right_keys",
        "_stage",
        "_triggers",
    )
    _stage: Stage
    _layout: GamepadLayout
    _dead_zone: float
    _key_buttons: dict[Key, GamepadButton]
    _left_keys: _StickKeys
    _right_keys: _StickKeys
    _device: Controller | None
    _buttons: frozenset[int]
    _left: Point
    _right: Point
    _triggers: tuple[float, float]

    def __init__(self) -> None:
        raise TypeError("Use stage.gamepads[index]; Gamepad slots belong to a Stage")

    @property
    def index(self) -> int:
        """This player's zero-based slot, unchanged by physical disconnection."""
        return self._stage.gamepads.index(self)

    @property
    def connected(self) -> bool:
        """Whether physical hardware is associated; keyboard-only input still works."""
        if self._device is None:
            return False
        return bool(self._device.attached())

    @property
    def remote_connected(self) -> bool:
        """Whether this slot has an active remote player with a live game view."""
        if self._stage._network is None:
            return False
        from ._network import remote_connected

        return remote_connected(self)

    def _nonlocal(self) -> bool:
        if self in self._stage._bots:
            return True
        if self._stage._network is None:
            return False
        from ._network import nonlocal_slot

        return nonlocal_slot(self)

    @property
    def name(self) -> str | None:
        """The hardware's diagnostic name, or None without an attached device."""
        if self._device is None:
            return None
        return str(self._device.name) if self.connected else None

    @property
    def layout(self) -> GamepadLayout:
        """Face-button convention; changing it does not invent press events."""
        return self._layout

    @layout.setter
    def layout(self, value: GamepadLayout) -> None:
        self._open()
        if not isinstance(value, GamepadLayout):
            raise TypeError("Use GamepadLayout.XBOX or NINTENDO")
        self._layout = value
        self._rebaseline()

    @property
    def dead_zone(self) -> float:
        """Radial physical-stick dead zone in [0, 1); default 0.2."""
        return self._dead_zone

    @dead_zone.setter
    def dead_zone(self, value: float) -> None:
        self._open()
        value = _number(value, "dead_zone", minimum=0)
        if value >= 1:
            raise ValueError("dead_zone must be less than 1")
        self._dead_zone = value

    @property
    def left_stick(self) -> Point:
        """Combined left stick: x right/y up, with vector magnitude at most one."""
        return self._left if self._nonlocal() else self._stick(self._left, self._left_keys)

    @property
    def right_stick(self) -> Point:
        """Combined right stick; keyboard mapping and dead zone match left_stick."""
        return self._right if self._nonlocal() else self._stick(self._right, self._right_keys)

    @property
    def left_trigger(self) -> float:
        """Current left trigger pressure in [0, 1], zero when unavailable."""
        return self._triggers[0]

    @property
    def right_trigger(self) -> float:
        """Current right trigger pressure in [0, 1], zero when unavailable."""
        return self._triggers[1]

    def is_down(self, button: GamepadButton) -> bool:
        """True while the physical button or any mapped key is held."""
        if not isinstance(button, GamepadButton):
            raise TypeError("Use a GamepadButton enum value")
        return _button_index(button, self.layout) in self._buttons or (
            not self._nonlocal()
            and any(
                mapped is button and key in self._stage._held_keys
                for key, mapped in self._key_buttons.items()
            )
        )

    def map_key(self, key: Key, button: GamepadButton | None) -> None:
        """Map one key to a logical button; None removes that key's button mapping.

        Several keys may hold one button; gameplay observes logical button events.
        Configuration edits require a fresh press before they produce events.
        """
        self._open()
        if not isinstance(key, Key) or (
            button is not None and not isinstance(button, GamepadButton)
        ):
            raise TypeError("Use Key and GamepadButton values (or None to unmap)")
        if button is None:
            self._key_buttons.pop(key, None)
        else:
            self._key_buttons[key] = button
        self._rebaseline()

    def map_left_stick(
        self,
        *,
        left: Key | None = None,
        right: Key | None = None,
        up: Key | None = None,
        down: Key | None = None,
    ) -> None:
        """Replace all left-stick key bindings; an empty call clears them."""
        self._open()
        self._left_keys = _keys(left, right, up, down)
        self._rebaseline()

    def map_right_stick(
        self,
        *,
        left: Key | None = None,
        right: Key | None = None,
        up: Key | None = None,
        down: Key | None = None,
    ) -> None:
        """Replace all right-stick key bindings; opposite directions cancel."""
        self._open()
        self._right_keys = _keys(left, right, up, down)
        self._rebaseline()

    def clear_keyboard(self) -> None:
        """Remove this slot's button/stick mappings, leaving other players unchanged."""
        self._open()
        self._key_buttons.clear()
        self._left_keys = self._right_keys = (None, None, None, None)
        self._rebaseline()

    def _open(self) -> None:
        if self._stage._state == "closed":
            raise StageError("This gamepad's stage is closed")
        if self._stage._state == "running" and self._nonlocal():
            raise StageError("Remote/automated slot settings cannot change during play")

    def _rebaseline(self) -> None:
        from ._gamepads import _rebaseline

        _rebaseline(self)

    def _stick(self, physical: Point, keys: _StickKeys) -> Point:
        held = tuple(key is not None and key in self._stage._held_keys for key in keys)
        if any(held):
            x, y = float(held[1]) - held[0], float(held[2]) - held[3]
            magnitude = max(1.0, hypot(x, y))
            return x / magnitude, y / magnitude
        magnitude = hypot(*physical)
        if magnitude <= self.dead_zone:
            return 0.0, 0.0
        scale = (min(1.0, magnitude) - self.dead_zone) / ((1 - self.dead_zone) * magnitude)
        return physical[0] * scale, physical[1] * scale


def _keys(left: Key | None, right: Key | None, up: Key | None, down: Key | None) -> _StickKeys:
    keys = (left, right, up, down)
    if any(key is not None and not isinstance(key, Key) for key in keys):
        raise TypeError("Stick directions must be Key values or None")
    return keys


def _button_index(button: GamepadButton, layout: GamepadLayout) -> int:
    """Translate logical labels to standard physical positions, never device IDs."""
    face = (GamepadButton.A, GamepadButton.B, GamepadButton.X, GamepadButton.Y)
    if button in face:
        return ((0, 1, 2, 3) if layout is GamepadLayout.XBOX else (1, 0, 3, 2))[face.index(button)]
    return {
        GamepadButton.L: 4,
        GamepadButton.R: 5,
        GamepadButton.SELECT: 8,
        GamepadButton.START: 9,
        GamepadButton.LEFT_STICK: 10,
        GamepadButton.RIGHT_STICK: 11,
        GamepadButton.UP: 12,
        GamepadButton.DOWN: 13,
        GamepadButton.LEFT: 14,
        GamepadButton.RIGHT: 15,
    }[button]


def _new_gamepad(stage: Stage, layout: GamepadLayout, index: int) -> Gamepad:
    slot = object.__new__(Gamepad)
    slot._stage, slot._layout, slot._dead_zone = stage, layout, 0.2
    slot._key_buttons = {}
    slot._left_keys = slot._right_keys = (None, None, None, None)
    if index < 2:
        left, right, up, down, a, b = (
            (Key.A, Key.D, Key.W, Key.S, Key.SPACE, Key.F)
            if index == 0
            else (Key.LEFT, Key.RIGHT, Key.UP, Key.DOWN, Key.ENTER, Key.RIGHT_SHIFT)
        )
        slot._left_keys = (left, right, up, down)
        slot._key_buttons = {
            left: GamepadButton.LEFT,
            right: GamepadButton.RIGHT,
            up: GamepadButton.UP,
            down: GamepadButton.DOWN,
            a: GamepadButton.A,
            b: GamepadButton.B,
        }
    slot._device = None
    slot._buttons = frozenset()
    slot._left = slot._right = (0.0, 0.0)
    slot._triggers = (0.0, 0.0)
    return slot
