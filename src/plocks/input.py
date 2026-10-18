"""Discoverable input names and the sole owners of held-input state."""

from __future__ import annotations

from enum import IntEnum, StrEnum

from .geometry import Point


class Key(StrEnum):
    """A keyboard key used to configure logical gamepad mappings."""

    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    SPACE = "space"
    ENTER = "return"
    ESCAPE = "escape"
    TAB = "tab"
    BACKSPACE = "backspace"
    DELETE = "delete"
    HOME = "home"
    END = "end"
    PAGE_UP = "page up"
    PAGE_DOWN = "page down"
    LEFT_SHIFT = "left shift"
    RIGHT_SHIFT = "right shift"
    LEFT_CTRL = "left ctrl"
    RIGHT_CTRL = "right ctrl"
    LEFT_ALT = "left alt"
    RIGHT_ALT = "right alt"
    A = "a"
    B = "b"
    C = "c"
    D = "d"
    E = "e"
    F = "f"
    G = "g"
    H = "h"
    I = "i"
    J = "j"
    K = "k"
    L = "l"
    M = "m"
    N = "n"
    O = "o"
    P = "p"
    Q = "q"
    R = "r"
    S = "s"
    T = "t"
    U = "u"
    V = "v"
    W = "w"
    X = "x"
    Y = "y"
    Z = "z"
    ZERO = "0"
    ONE = "1"
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"


class MouseButton(IntEnum):
    """A mouse button; wheel scrolling is not a button in this API."""

    LEFT = 1
    MIDDLE = 2
    RIGHT = 3


class Mouse:
    """Read mouse position in centered stage coordinates and held buttons."""

    __slots__ = ("_down", "_position")

    def __init__(self) -> None:
        self._position: Point = (0, 0)
        self._down: set[MouseButton] = set()

    @property
    def position(self) -> Point:
        """Current (x, y), with y upward; the world camera does not change this."""
        return self._position

    def is_down(self, button: MouseButton) -> bool:
        """True while this mouse button is held."""
        return button in self._down
