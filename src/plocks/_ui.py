"""Local UI painting, clipped hit testing and focused logical-button dispatch."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from ._ui_layout import _available, _clip, _control_rect, _font
from .events import Event, GamepadPress
from .gamepads import GamepadButton
from .geometry import Color, Point
from .ui import Button, Label, Panel, ProgressBar

if TYPE_CHECKING:
    from .stage import Stage


_MENU = frozenset(
    (GamepadButton.UP, GamepadButton.DOWN, GamepadButton.LEFT, GamepadButton.RIGHT, GamepadButton.A)
)


def _menu_key(stage: Stage, button: GamepadButton) -> bool:
    return stage._alert is not None or (stage._ui_focus is not None and button in _MENU)


def _activate(stage: Stage, button: Button) -> None:
    from .stage import _check_callback_result

    for callback in tuple(button._clicks):
        if not stage.running or stage._alert is not None or not _available(stage, button):
            break
        _check_callback_result(callback(Event(stage, button, None)), "button")


def _buttons(stage: Stage) -> list[Button]:
    """Walk the sole root/child membership owners; no retained UI registry."""
    result: list[Button] = []
    for root in sorted(stage._members, key=lambda obj: obj.layer):
        if isinstance(root, Panel) and root.visible:
            result.extend(
                child
                for child in sorted(root._children, key=lambda obj: obj.layer)
                if isinstance(child, Button) and _available(stage, child)
            )
        elif isinstance(root, Button) and _available(stage, root):
            result.append(root)
    return result


def _key(stage: Stage, event: GamepadPress) -> bool:
    """Consume menu edges only while explicit focus is active; no repeat timer."""
    if stage._alert is not None:
        return True
    focus = stage._ui_focus
    if focus is None or not _menu_key(stage, event.button):
        return False
    if stage._pause_reasons - {"user"}:
        return True
    buttons = _buttons(stage)
    if focus not in buttons:
        stage._ui_focus = None
        return False
    if event.button is GamepadButton.A:
        _activate(stage, focus)
    else:
        delta = -1 if event.button in (GamepadButton.UP, GamepadButton.LEFT) else 1
        stage.focus(buttons[(buttons.index(focus) + delta) % len(buttons)])
    return True


def _hit(stage: Stage, position: Point) -> Button | Panel | None:
    point = stage.to_screen(position, world=False)
    ordered = sorted(stage._members, key=lambda obj: obj.layer)
    for root in reversed(ordered):
        if isinstance(root, Panel) and root.visible:
            rect = _control_rect(stage, root)
            if rect.collidepoint(point):
                children = sorted(root._children, key=lambda obj: obj.layer)
                for child in reversed(children):
                    if (
                        isinstance(child, Button)
                        and child.visible
                        and _control_rect(stage, child).clip(rect).collidepoint(point)
                    ):
                        return child
                return root
        elif isinstance(root, Button) and root.visible:
            if _control_rect(stage, root).collidepoint(point):
                return root
    return None


def _click(stage: Stage, button: Button | Panel) -> None:
    if (
        isinstance(button, Button)
        and _available(stage, button)
        and not (stage._pause_reasons - {"user"})
    ):
        stage.focus(button)
        _activate(stage, button)


def _box(
    target: pygame.Surface,
    rect: pygame.Rect,
    color: Color,
    *,
    radius: int = 0,
    width: int = 0,
) -> None:
    """Alpha-composite a local scratch surface; native direct draws ignore fill alpha."""
    visible = rect.clip(target.get_clip()).clip(target.get_rect())
    if not visible:
        return
    surface = pygame.Surface(visible.size, pygame.SRCALPHA)
    local = rect.move(-visible.left, -visible.top)
    pygame.draw.rect(surface, color, local, width, border_radius=radius)
    target.blit(surface, visible.topleft)


def _draw(stage: Stage, target: pygame.Surface, obj: Label | Button | ProgressBar | Panel) -> None:
    """Paint from current settings; measured geometry/fonts exist only for this operation."""
    if isinstance(obj, Panel):
        _box(target, _control_rect(stage, obj), obj.color, radius=stage.ui_theme.corner_radius)
        previous = target.get_clip()
        target.set_clip(previous.clip(_control_rect(stage, obj)))
        try:
            for child in sorted(obj._children, key=lambda control: control.layer):
                if child.visible:
                    _draw(stage, target, child)
        finally:
            target.set_clip(previous)
        return
    previous = target.get_clip()
    target.set_clip(previous.clip(_clip(stage, obj)))
    try:
        if isinstance(obj, Label):
            font = _font(obj.size)
            rect = _control_rect(stage, obj, font=font)
            _label(target, obj, rect, font)
        else:
            _draw_control(stage, target, obj, _control_rect(stage, obj))
    finally:
        target.set_clip(previous)


def _label(target: pygame.Surface, obj: Label, rect: pygame.Rect, font: pygame.font.Font) -> None:
    """Borrow the font used for measurement for this same paint operation."""
    for index, line in enumerate(obj.text.split("\n")):
        image = font.render(line.rstrip("\r"), False, obj.color)
        x = rect.left + round((rect.width - image.get_width()) * obj.anchor.value[0])
        target.blit(image, (x, rect.top + index * font.get_linesize()))


def _draw_control(
    stage: Stage,
    target: pygame.Surface,
    obj: Button | ProgressBar,
    rect: pygame.Rect,
) -> None:
    theme = stage.ui_theme
    if isinstance(obj, ProgressBar):
        _box(target, rect, theme.panel_color)
        filled = rect.copy()
        filled.width = round(rect.width * (obj.value / obj.maximum))
        if filled.width:
            _box(target, filled, obj.color)
        _box(target, rect, theme.muted_color, width=1)
        return
    focused = stage._ui_focus is obj
    hovered = _hit(stage, stage.mouse.position) is obj
    _box(
        target,
        rect,
        theme.button_color if obj.enabled else theme.panel_color,
        radius=theme.corner_radius,
    )
    _box(
        target,
        rect,
        theme.accent_color if focused or hovered else theme.muted_color,
        radius=theme.corner_radius,
        width=3 if focused else 2 if hovered else 1,
    )
    image = _font(obj.text_size).render(
        obj.text,
        False,
        theme.text_color if obj.enabled else theme.muted_color,
    )
    padding = min(theme.padding, max(0, (min(rect.size) - 1) // 2))
    target.set_clip(target.get_clip().clip(rect.inflate(-2 * padding, -2 * padding)))
    target.blit(image, image.get_rect(center=rect.center))
