"""One stage-owned modal record; all text, panel and button geometry is local."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from .events import Event, GamepadPress
from .gamepads import GamepadButton
from .input import MouseButton
from .theme import AlertLevel, _level_color

if TYPE_CHECKING:
    from .stage import Stage, _InputEvent


@dataclass(frozen=True, slots=True)
class _Alert:
    text: str
    button_text: str
    level: AlertLevel
    on_close: Callable[[Event[Stage, None]], None] | None


def _reset_input(stage: Stage) -> None:
    from ._gamepads import _clear_repeats

    _clear_repeats(stage)
    stage._pending[:] = [
        event for event in stage._pending if not isinstance(event, (GamepadPress, tuple))
    ]


def _ellipsize(text: str, font: pygame.font.Font, width: int) -> str:
    while text and font.size(text + "...")[0] > width:
        text = text[:-1]
    return text + "..."


def _wrap(text: str, font: pygame.font.Font, width: int) -> tuple[str, ...]:
    """Keep explicit newlines and split oversized words without storing measured text."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.rstrip("\r").split():
            if current and font.size(current + " " + word)[0] > width:
                lines.append(current)
                current = ""
            if font.size(word)[0] > width:
                for character in word:
                    if current and font.size(current + character)[0] > width:
                        lines.append(current)
                        current = ""
                    current += character
            else:
                current = (current + " " + word).strip()
        lines.append(current)
    return tuple(lines)


def _layout(
    stage: Stage,
    alert: _Alert,
) -> tuple[pygame.Rect, pygame.Rect, pygame.font.Font, tuple[str, ...], int]:
    """Fit to the viewport each operation, including live theme size/padding changes."""
    from ._ui_layout import _font

    theme = stage.ui_theme
    padding = min(theme.padding, min(stage.width, stage.height) // 12)
    size = min(theme.text_size, max(1, (stage.height - 6 * padding) // 5))
    font = _font(size)
    line_height = font.get_linesize()
    width = max(1, min(480, stage.width - 2 * padding))
    available = max(1, stage.height - 2 * padding)
    text_width = max(1, width - 2 * padding)
    button_height = min(line_height + 2 * padding, max(1, available // 3))
    limit = max(0, (available - line_height - button_height - 4 * padding) // line_height)
    lines = _wrap(alert.text, font, text_width)
    if len(lines) > limit:
        lines = (
            (*lines[: max(0, limit - 1)], _ellipsize(lines[limit - 1], font, text_width))
            if limit
            else ()
        )
    height = min(available, line_height * (1 + len(lines)) + button_height + 4 * padding)
    panel = pygame.Rect(0, 0, width, max(1, height))
    panel.center = (stage.width // 2, stage.height // 2)
    button = pygame.Rect(
        panel.left + padding,
        panel.bottom - padding - button_height,
        max(1, width - 2 * padding),
        button_height,
    )
    return panel, button, font, lines, padding


def _draw(stage: Stage, target: pygame.Surface) -> None:
    alert = stage._alert
    if alert is None:
        return
    from ._ui import _box

    panel, button, font, lines, padding = _layout(stage, alert)
    theme = stage.ui_theme
    _box(target, target.get_rect(), (0, 0, 0, 160))
    _box(target, panel, theme.panel_color, radius=theme.corner_radius)
    _box(target, panel, _level_color(theme, alert.level), radius=theme.corner_radius, width=3)
    previous = target.get_clip()
    target.set_clip(previous.clip(panel))
    try:
        heading = font.render(alert.level.value.title(), False, theme.text_color)
        target.blit(heading, (panel.left + padding, panel.top + padding))
        for index, line in enumerate(lines, 1):
            image = font.render(line, False, theme.text_color)
            target.blit(
                image, (panel.left + padding, panel.top + padding + index * font.get_linesize())
            )
        _box(target, button, theme.button_color, radius=theme.corner_radius)
        _box(target, button, theme.accent_color, radius=theme.corner_radius, width=3)
        text = alert.button_text
        if font.size(text)[0] > button.width - 2 * padding:
            text = _ellipsize(text, font, max(1, button.width - 2 * padding))
        target.set_clip(target.get_clip().clip(button))
        image = font.render(text, False, theme.text_color)
        target.blit(image, image.get_rect(center=button.center))
    finally:
        target.set_clip(previous)


def _dismiss(stage: Stage) -> None:
    alert = stage._alert
    if alert is None:
        return
    stage._alert = None
    _reset_input(stage)
    stage._set_pause("alert", False)
    if alert.on_close is not None:
        from .stage import _check_callback_result

        _check_callback_result(alert.on_close(Event(stage, stage, None)), "alert")


def _input(stage: Stage, event: _InputEvent) -> None:
    """Acknowledge only the current modal; every other game input is consumed."""
    alert = stage._alert
    if alert is None or stage._pause_reasons - {"user", "alert"}:
        return
    if isinstance(event, GamepadPress) and event.button is GamepadButton.A:
        _dismiss(stage)
    elif isinstance(event, tuple) and event[1] is MouseButton.LEFT:
        _, button, _, _, _ = _layout(stage, alert)
        if button.collidepoint(stage.to_screen(event[0], world=False)):
            _dismiss(stage)
