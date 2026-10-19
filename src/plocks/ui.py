"""Small screen-coordinate labels, buttons and progress bars."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import pygame

from .events import Event
from .geometry import Color, Point, _integer, _number, _point, _positive

if TYPE_CHECKING:
    from .stage import Stage


def _text(value: str, *, multiline: bool = True) -> str:
    if not isinstance(value, str):
        raise TypeError("text must be str")
    if not multiline and ("\n" in value or "\r" in value):
        raise ValueError("Button text must be a single line")
    return value


def _blur(button: Button) -> None:
    if button._stage is not None and button._stage._ui_focus is button:
        button._stage._ui_focus = None


class Label:
    """Persistent screen text; add it with stage.add(label). Newlines are supported.

    Position is its center. Labels use the bundled default font and do not capture
    input. Change text to update a score without a drawing callback.
    """

    __slots__ = ("_color", "_layer", "_position", "_size", "_stage", "_text", "_visible")

    def __init__(
        self,
        text: str,
        *,
        position: Point = (0, 0),
        size: int = 24,
        color: Color = "white",
        layer: int = 0,
    ) -> None:
        self._stage: Stage | None = None
        self.text = text
        self.position = position
        self.size = size
        self.color = color
        self.visible = True
        self.layer = layer

    @property
    def text(self) -> str:
        """Current displayed text. Assign ordinary Python strings or f-strings."""
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self._text = _text(value)

    @property
    def size(self) -> int:
        """Positive font size in logical screen pixels."""
        return self._size

    @size.setter
    def size(self, value: int) -> None:
        self._size = _integer(value, "size", minimum=1)

    @property
    def color(self) -> Color:
        """Text/fill color as a name or RGB/RGBA tuple."""
        return self._color

    @color.setter
    def color(self, value: Color) -> None:
        pygame.Color(value)
        self._color = value

    @property
    def position(self) -> Point:
        """Visual center in screen coordinates; x right, y up; camera-independent."""
        return self._position

    @position.setter
    def position(self, value: Point) -> None:
        self._position = _point(value)

    @property
    def layer(self) -> int:
        """UI painting order; higher layers and later additions appear on top."""
        return self._layer

    @layer.setter
    def layer(self, value: int) -> None:
        self._layer = _integer(value, "layer")

    @property
    def visible(self) -> bool:
        """Whether this screen control is drawn and available to input."""
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("visible must be bool")
        self._visible = value


class Button:
    """A screen button with a readable default style and a visible focus outline.

    Add with stage.add(button). Left mouse press activates the topmost button;
    stage.focus(button) enables directional/A menu controls. Handlers receive
    Event[Button, None], run while user-paused, and must return None.
    """

    __slots__ = (
        "_clicks",
        "_enabled",
        "_height",
        "_layer",
        "_position",
        "_stage",
        "_text",
        "_text_size",
        "_visible",
        "_width",
    )

    def __init__(
        self,
        text: str,
        *,
        position: Point = (0, 0),
        width: float = 140,
        height: float = 44,
        text_size: int = 24,
        layer: int = 0,
    ) -> None:
        self._stage: Stage | None = None
        self._clicks: list[Callable[[Event[Button, None]], None]] = []
        self.text = text
        self.position = position
        self.width = width
        self.height = height
        self.text_size = text_size
        self.visible = True
        self.enabled = True
        self.layer = layer

    def on_click(
        self, callback: Callable[[Event[Button, None]], None]
    ) -> Callable[[Event[Button, None]], None]:
        """Register synchronous callback(event); use event.target for this button.

        May register before attachment. Mouse and focused A-button activation use
        the same event, with source=Stage and data=None. Must return None.
        """
        from .stage import _sync

        _sync(callback, "button")
        self._clicks.append(callback)
        return callback

    @property
    def enabled(self) -> bool:
        """Whether this button can activate; disabling clears its menu focus."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("enabled must be bool")
        self._enabled = value
        if not value:
            _blur(self)

    @property
    def text(self) -> str:
        """Current displayed text. Assign ordinary Python strings or f-strings."""
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self._text = _text(value, multiline=False)

    @property
    def width(self) -> float:
        """Positive button width in logical screen pixels."""
        return self._width

    @width.setter
    def width(self, value: float) -> None:
        self._width = _positive(value, "width")

    @property
    def height(self) -> float:
        """Positive button height in logical screen pixels."""
        return self._height

    @height.setter
    def height(self, value: float) -> None:
        self._height = _positive(value, "height")

    @property
    def text_size(self) -> int:
        """Positive font size in logical screen pixels."""
        return self._text_size

    @text_size.setter
    def text_size(self, value: int) -> None:
        self._text_size = _integer(value, "text_size", minimum=1)

    @property
    def position(self) -> Point:
        """Visual center in screen coordinates; x right, y up; camera-independent."""
        return self._position

    @position.setter
    def position(self, value: Point) -> None:
        self._position = _point(value)

    @property
    def layer(self) -> int:
        """UI painting order; higher layers and later additions appear on top."""
        return self._layer

    @layer.setter
    def layer(self, value: int) -> None:
        self._layer = _integer(value, "layer")

    @property
    def visible(self) -> bool:
        """Whether this screen control is drawn and available to input."""
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("visible must be bool")
        self._visible = value
        if not value:
            _blur(self)


class ProgressBar:
    """A screen meter, such as health. Values must stay between zero and maximum.

    Add with stage.add(bar); assign value from ordinary game state. Changing
    maximum below the current value raises ValueError before mutation.
    """

    __slots__ = (
        "_color",
        "_height",
        "_layer",
        "_maximum",
        "_position",
        "_stage",
        "_value",
        "_visible",
        "_width",
    )

    def __init__(
        self,
        *,
        value: float = 0,
        maximum: float = 100,
        position: Point = (0, 0),
        width: float = 160,
        height: float = 18,
        color: Color = "limegreen",
        layer: int = 0,
    ) -> None:
        self._stage: Stage | None = None
        self._value = 0.0
        self.maximum = maximum
        self.value = value
        self.position = position
        self.width = width
        self.height = height
        self.color = color
        self.visible = True
        self.layer = layer

    @property
    def value(self) -> float:
        """Filled amount, from zero through maximum inclusive."""
        return self._value

    @value.setter
    def value(self, value: float) -> None:
        amount = _number(value, "value", minimum=0)
        if amount > self.maximum:
            raise ValueError("value must not exceed maximum")
        self._value = amount

    @property
    def maximum(self) -> float:
        """Positive amount represented by a full bar."""
        return self._maximum

    @maximum.setter
    def maximum(self, value: float) -> None:
        amount = _positive(value, "maximum")
        if self.value > amount:
            raise ValueError("maximum must not be below value")
        self._maximum = amount

    @property
    def width(self) -> float:
        """Positive meter width in logical screen pixels."""
        return self._width

    @width.setter
    def width(self, value: float) -> None:
        self._width = _positive(value, "width")

    @property
    def height(self) -> float:
        """Positive meter height in logical screen pixels."""
        return self._height

    @height.setter
    def height(self, value: float) -> None:
        self._height = _positive(value, "height")

    @property
    def color(self) -> Color:
        """Text/fill color as a name or RGB/RGBA tuple."""
        return self._color

    @color.setter
    def color(self, value: Color) -> None:
        pygame.Color(value)
        self._color = value

    @property
    def position(self) -> Point:
        """Visual center in screen coordinates; x right, y up; camera-independent."""
        return self._position

    @position.setter
    def position(self, value: Point) -> None:
        self._position = _point(value)

    @property
    def layer(self) -> int:
        """UI painting order; higher layers and later additions appear on top."""
        return self._layer

    @layer.setter
    def layer(self, value: int) -> None:
        self._layer = _integer(value, "layer")

    @property
    def visible(self) -> bool:
        """Whether this screen control is drawn and available to input."""
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("visible must be bool")
        self._visible = value
