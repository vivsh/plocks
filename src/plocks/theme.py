"""Small immutable color and spacing definitions shared by screen controls."""

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import pygame

from .geometry import Color, _integer

if TYPE_CHECKING:
    from .stage import Stage


class AlertLevel(Enum):
    """Presentation of an alert; every level has the same dismissal behavior."""

    INFO = "info"
    WARNING = "warning"
    SUCCESS = "success"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class UITheme:
    """Shared screen-control colors and logical-pixel sizes.

    Pass to Stage(ui_theme=...) or replace stage.ui_theme for a live restyle.
    Explicit control overrides take priority. Text size must be positive;
    padding and corner radius must be nonnegative integers. Colors follow Color.
    The bundled font is used; no font or measured layout is retained here.
    """

    text_color: Color = "white"
    panel_color: Color = "#293340"
    button_color: Color = "#33465b"
    accent_color: Color = "#60a5fa"
    muted_color: Color = "#9aa7b3"
    text_size: int = 24
    padding: int = 12
    corner_radius: int = 8
    info_color: Color = "#60a5fa"
    warning_color: Color = "#fbbf24"
    success_color: Color = "#4ade80"
    error_color: Color = "#f87171"

    def __post_init__(self) -> None:
        for color in (
            self.text_color,
            self.panel_color,
            self.button_color,
            self.accent_color,
            self.muted_color,
            self.info_color,
            self.warning_color,
            self.success_color,
            self.error_color,
        ):
            _validate_color(color)
        _integer(self.text_size, "text_size", minimum=1)
        _integer(self.padding, "padding", minimum=0)
        _integer(self.corner_radius, "corner_radius", minimum=0)


def _validate_color(value: Color) -> None:
    """Keep frozen themes and inherited overrides limited to immutable Color values."""
    if not isinstance(value, (str, tuple)):
        raise TypeError("color must be a named string or RGB/RGBA tuple")
    if isinstance(value, tuple) and (
        len(value) not in (3, 4)
        or any(
            isinstance(channel, bool) or not isinstance(channel, int) or not 0 <= channel <= 255
            for channel in value
        )
    ):
        raise ValueError("color channels must be integers from 0 through 255")
    pygame.Color(value)


_DEFAULT_THEME = UITheme()


def _theme(stage: "Stage | None") -> UITheme:
    return _DEFAULT_THEME if stage is None else stage.ui_theme


def _level_color(theme: UITheme, level: AlertLevel) -> Color:
    match level:
        case AlertLevel.INFO:
            return theme.info_color
        case AlertLevel.WARNING:
            return theme.warning_color
        case AlertLevel.SUCCESS:
            return theme.success_color
        case AlertLevel.ERROR:
            return theme.error_color
