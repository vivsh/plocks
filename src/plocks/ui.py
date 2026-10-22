"""Small screen-coordinate labels, buttons and progress bars."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from .events import Event
from .geometry import Color, Point, _integer, _number, _point, _positive
from .imaging import Anchor
from .theme import _theme, _validate_color

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


def _check_focus(control: Button | Panel) -> None:
    """A clipped descendant must not leave the menu pointing at an unavailable button."""
    stage = control._stage
    if stage is None or stage._ui_focus is None:
        return
    from ._ui_layout import _available

    if not _available(stage, stage._ui_focus):
        stage._ui_focus = None


class Label:
    """Persistent screen text; add it with stage.add(label). Newlines are supported.

    Position names its anchor (CENTER by default). Labels use the bundled font and do not capture
    input. Change text to update a score without a drawing callback.
    """

    __slots__ = (
        "_anchor",
        "_color",
        "_layer",
        "_panel",
        "_position",
        "_size",
        "_stage",
        "_text",
        "_visible",
    )

    def __init__(
        self,
        text: str,
        *,
        position: Point = (0, 0),
        size: int | None = None,
        color: Color | None = None,
        anchor: Anchor = Anchor.CENTER,
        layer: int = 0,
    ) -> None:
        self._stage: Stage | None = None
        self._panel: Panel | None = None
        self.anchor = anchor
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
        """Font size in logical pixels; assign None to inherit the current stage theme."""
        return _theme(self._stage).text_size if self._size is None else self._size

    @size.setter
    def size(self, value: int | None) -> None:
        self._size = None if value is None else _integer(value, "size", minimum=1)

    @property
    def color(self) -> Color:
        """Resolved color; assign a Color override or None to inherit the current theme."""
        return _theme(self._stage).text_color if self._color is None else self._color

    @color.setter
    def color(self, value: Color | None) -> None:
        if value is not None:
            _validate_color(value)
        self._color = value

    @property
    def anchor(self) -> Anchor:
        """Point of the control placed at position; defaults to Anchor.CENTER."""
        return self._anchor

    @anchor.setter
    def anchor(self, value: Anchor) -> None:
        if not isinstance(value, Anchor):
            raise TypeError("anchor must be an Anchor")
        self._anchor = value

    @property
    def position(self) -> Point:
        """Anchor position: screen coordinates, or local to a containing panel; x right, y up."""
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
        "_anchor",
        "_clicks",
        "_enabled",
        "_height",
        "_layer",
        "_panel",
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
        text_size: int | None = None,
        anchor: Anchor = Anchor.CENTER,
        layer: int = 0,
    ) -> None:
        self._stage: Stage | None = None
        self._panel: Panel | None = None
        self.anchor = anchor
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
        _check_focus(self)

    @property
    def height(self) -> float:
        """Positive button height in logical screen pixels."""
        return self._height

    @height.setter
    def height(self, value: float) -> None:
        self._height = _positive(value, "height")
        _check_focus(self)

    @property
    def text_size(self) -> int:
        """Font size in logical pixels; assign None to inherit the current stage theme."""
        return _theme(self._stage).text_size if self._text_size is None else self._text_size

    @text_size.setter
    def text_size(self, value: int | None) -> None:
        self._text_size = None if value is None else _integer(value, "text_size", minimum=1)

    @property
    def anchor(self) -> Anchor:
        """Point of the control placed at position; defaults to Anchor.CENTER."""
        return self._anchor

    @anchor.setter
    def anchor(self, value: Anchor) -> None:
        if not isinstance(value, Anchor):
            raise TypeError("anchor must be an Anchor")
        self._anchor = value
        _check_focus(self)

    @property
    def position(self) -> Point:
        """Anchor position: screen coordinates, or local to a containing panel; x right, y up."""
        return self._position

    @position.setter
    def position(self, value: Point) -> None:
        self._position = _point(value)
        _check_focus(self)

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
        "_anchor",
        "_color",
        "_height",
        "_layer",
        "_maximum",
        "_panel",
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
        color: Color | None = None,
        anchor: Anchor = Anchor.CENTER,
        layer: int = 0,
    ) -> None:
        self._stage: Stage | None = None
        self._panel: Panel | None = None
        self.anchor = anchor
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
        """Resolved color; assign a Color override or None to inherit the current theme."""
        return _theme(self._stage).accent_color if self._color is None else self._color

    @color.setter
    def color(self, value: Color | None) -> None:
        if value is not None:
            _validate_color(value)
        self._color = value

    @property
    def anchor(self) -> Anchor:
        """Point of the control placed at position; defaults to Anchor.CENTER."""
        return self._anchor

    @anchor.setter
    def anchor(self, value: Anchor) -> None:
        if not isinstance(value, Anchor):
            raise TypeError("anchor must be an Anchor")
        self._anchor = value

    @property
    def position(self) -> Point:
        """Anchor position: screen coordinates, or local to a containing panel; x right, y up."""
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


class Panel:
    """A colored screen overlay containing one level of ordinary UI controls.

    Add controls with panel.add(), then add the panel with stage.add(panel).
    Child positions are relative to the panel's center, x right and y up.
    Moving/hiding the panel affects its children; drawing and clicks clip to its
    rectangle. Panels cannot nest. RGBA color tuples provide translucency;
    color=None inherits the stage theme. No automatic layout is performed.
    """

    __slots__ = (
        "_anchor",
        "_children",
        "_color",
        "_height",
        "_layer",
        "_position",
        "_stage",
        "_visible",
        "_width",
    )

    def __init__(
        self,
        *,
        position: Point = (0, 0),
        width: float = 300,
        height: float = 180,
        color: Color | None = None,
        anchor: Anchor = Anchor.CENTER,
        layer: int = 0,
    ) -> None:
        self._stage: Stage | None = None
        self._children: list[Label | Button | ProgressBar] = []
        self.position = position
        self.width = width
        self.height = height
        self.color = color
        self.anchor = anchor
        self.visible = True
        self.layer = layer

    @property
    def children(self) -> tuple[Label | Button | ProgressBar, ...]:
        """Read-only membership snapshot; use add/remove/clear to change children."""
        return tuple(self._children)

    def add(self, control: Label | Button | ProgressBar) -> None:
        """Attach a detached control once; actors and nested panels are rejected.

        A child belongs to one panel. Detach a root from its stage or remove a
        child from its previous panel before adding it here. A staged panel also
        attaches the new child to its stage for theme/focus/event use.
        """
        from .errors import StageError
        from .stage import _open

        if self._stage is not None:
            _open(self._stage)
        if not isinstance(control, (Label, Button, ProgressBar)):
            raise TypeError("Panel children must be Label, Button or ProgressBar")
        if control in self._children:
            raise ValueError("This control is already in the panel")
        if control._stage is not None or control._panel is not None:
            raise StageError("Detach this control before adding it to a panel")
        self._children.append(control)
        control._panel = self
        control._stage = self._stage

    def remove(self, control: Label | Button | ProgressBar) -> None:
        """Detach a child, clearing its stage/focus and retaining its own settings."""
        if control not in self._children:
            raise ValueError("This control is not in the panel")
        if isinstance(control, Button):
            _blur(control)
        self._children.remove(control)
        control._panel = None
        control._stage = None

    def clear(self) -> None:
        """Remove all children; the panel remains attached and keeps its settings."""
        for control in tuple(self._children):
            self.remove(control)

    @property
    def position(self) -> Point:
        """Anchor position in centered screen coordinates; independent of the camera."""
        return self._position

    @position.setter
    def position(self, value: Point) -> None:
        self._position = _point(value)
        _check_focus(self)

    @property
    def width(self) -> float:
        """Positive width in logical screen pixels; children are clipped to this width."""
        return self._width

    @width.setter
    def width(self, value: float) -> None:
        self._width = _positive(value, "width")
        _check_focus(self)

    @property
    def height(self) -> float:
        """Positive height in logical screen pixels; children are clipped to this height."""
        return self._height

    @height.setter
    def height(self, value: float) -> None:
        self._height = _positive(value, "height")
        _check_focus(self)

    @property
    def color(self) -> Color:
        """Background fill; assign None to inherit the theme, or RGBA for translucency."""
        return _theme(self._stage).panel_color if self._color is None else self._color

    @color.setter
    def color(self, value: Color | None) -> None:
        if value is not None:
            _validate_color(value)
        self._color = value

    @property
    def anchor(self) -> Anchor:
        """Point of the panel placed at position; defaults to Anchor.CENTER."""
        return self._anchor

    @anchor.setter
    def anchor(self, value: Anchor) -> None:
        if not isinstance(value, Anchor):
            raise TypeError("anchor must be an Anchor")
        self._anchor = value
        _check_focus(self)

    @property
    def visible(self) -> bool:
        """Whether the panel and its children are drawn and available to input."""
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("visible must be bool")
        self._visible = value
        if not value:
            for child in self._children:
                if isinstance(child, Button):
                    _blur(child)

    @property
    def layer(self) -> int:
        """Root UI order; child layers are local to the panel."""
        return self._layer

    @layer.setter
    def layer(self, value: int) -> None:
        self._layer = _integer(value, "layer")
