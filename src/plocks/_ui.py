"""Local UI painting, hit testing and focused logical-button dispatch."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from .events import Event, GamepadPress
from .gamepads import GamepadButton
from .geometry import Point
from .ui import Button, Label, ProgressBar

if TYPE_CHECKING:
    from .stage import Stage


_MENU = frozenset(
    (GamepadButton.UP, GamepadButton.DOWN, GamepadButton.LEFT, GamepadButton.RIGHT, GamepadButton.A)
)


def _menu_key(stage: Stage, button: GamepadButton) -> bool:
    return stage._ui_focus is not None and button in _MENU


def _activate(stage: Stage, button: Button) -> None:
    from .stage import _check_callback_result

    for callback in tuple(button._clicks):
        if (
            not stage.running
            or button._stage is not stage
            or not button.visible
            or not button.enabled
        ):
            break
        _check_callback_result(callback(Event(stage, button, None)), "button")


def _key(stage: Stage, event: GamepadPress) -> bool:
    """Consume menu edges only while explicit focus is active; no repeat timer."""
    focus = stage._ui_focus
    if focus is None or not _menu_key(stage, event.button):
        return False
    if stage._pause_reasons - {"user"}:
        return True
    buttons = [
        b
        for b in sorted(stage._members, key=lambda m: m.layer)
        if isinstance(b, Button) and b.visible and b.enabled
    ]
    if focus not in buttons:
        stage._ui_focus = None
        return False
    if event.button is GamepadButton.A:
        _activate(stage, focus)
    else:
        delta = -1 if event.button in (GamepadButton.UP, GamepadButton.LEFT) else 1
        stage.focus(buttons[(buttons.index(focus) + delta) % len(buttons)])
    return True


def _hit(stage: Stage, position: Point) -> Button | None:
    x, y = position
    ordered = sorted(stage._members, key=lambda m: m.layer)
    for member in reversed(ordered):
        if isinstance(member, Button) and member.visible:
            cx, cy = member.position
            if (
                cx - member.width / 2 <= x < cx + member.width / 2
                and cy - member.height / 2 < y <= cy + member.height / 2
            ):
                return member
    return None


def _click(stage: Stage, button: Button) -> None:
    if (
        button._stage is stage
        and button.visible
        and button.enabled
        and not (stage._pause_reasons - {"user"})
    ):
        stage.focus(button)
        _activate(stage, button)


def _font(size: int) -> pygame.font.Font:
    if not pygame.font.get_init():
        pygame.font.init()
    return pygame.font.Font(None, size)


def _rect(stage: Stage, position: Point, width: float, height: float) -> pygame.Rect:
    x, y = stage.to_screen(position, world=False)
    result = pygame.Rect(0, 0, max(1, round(width)), max(1, round(height)))
    result.center = round(x), round(y)
    return result


def _draw(stage: Stage, target: pygame.Surface, obj: Label | Button | ProgressBar) -> None:
    """Create fonts/surfaces/rectangles for this draw only, retaining no layout."""
    if isinstance(obj, Label):
        font = _font(obj.size)
        lines = obj.text.split("\n")
        height = font.get_linesize() * len(lines)
        x, y = stage.to_screen(obj.position, world=False)
        for index, line in enumerate(lines):
            image = font.render(line.rstrip("\r"), False, obj.color)
            target.blit(
                image,
                (
                    round(x - image.get_width() / 2),
                    round(y - height / 2 + index * font.get_linesize()),
                ),
            )
        return
    rect = _rect(stage, obj.position, obj.width, obj.height)
    if isinstance(obj, ProgressBar):
        pygame.draw.rect(target, "#293340", rect)
        filled = rect.copy()
        filled.width = round(rect.width * (obj.value / obj.maximum))
        if filled.width:
            pygame.draw.rect(target, obj.color, filled)
        pygame.draw.rect(target, "#bec4cc", rect, 1)
        return
    hover = _hit(stage, stage.mouse.position) is obj
    fill = "#5d6670" if not obj.enabled else "#c6e6ff" if hover else "#f4f1e8"
    pygame.draw.rect(target, fill, rect, border_radius=5)
    pygame.draw.rect(
        target,
        "#358ad8" if stage._ui_focus is obj else "#75809a",
        rect,
        3 if stage._ui_focus is obj else 1,
        border_radius=5,
    )
    image = _font(obj.text_size).render(obj.text, False, "#182331" if obj.enabled else "#bec4cc")
    clip = target.get_clip()
    try:
        target.set_clip(rect.clip(clip))
        target.blit(image, image.get_rect(center=rect.center))
    finally:
        target.set_clip(clip)
