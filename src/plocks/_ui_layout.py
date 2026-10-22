"""Operation-local anchor geometry shared by UI painting and input."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from .geometry import Point
from .imaging import Anchor
from .ui import Button, Label, Panel, ProgressBar

if TYPE_CHECKING:
    from .stage import Stage


def _font(size: int) -> pygame.font.Font:
    if not pygame.font.get_init():
        pygame.font.init()
    return pygame.font.Font(None, size)


def _rect(
    stage: Stage,
    position: Point,
    width: float,
    height: float,
    anchor: Anchor = Anchor.CENTER,
) -> pygame.Rect:
    """Place exactly the rectangle painted and hit-tested in logical screen pixels."""
    x, y = stage.to_screen(position, world=False)
    w, h = max(1, round(width)), max(1, round(height))
    ax, ay = anchor.value
    return pygame.Rect(round(x - ax * w), round(y - ay * h), w, h)


def _control_rect(
    stage: Stage,
    obj: Label | Button | ProgressBar | Panel,
    *,
    font: pygame.font.Font | None = None,
) -> pygame.Rect:
    width: float
    height: float
    if isinstance(obj, Label):
        font = _font(obj.size) if font is None else font
        lines = obj.text.split("\n")
        width = max(font.size(line.rstrip("\r"))[0] for line in lines)
        height = font.get_linesize() * len(lines)
    else:
        width, height = obj.width, obj.height
    rect = _rect(stage, obj.position, width, height, obj.anchor)
    if not isinstance(obj, Panel) and obj._panel is not None:
        parent = _control_rect(stage, obj._panel)
        rect.move_ip(parent.centerx - stage.width // 2, parent.centery - stage.height // 2)
    return rect


def _clip(stage: Stage, obj: Label | Button | ProgressBar) -> pygame.Rect:
    viewport = pygame.Rect(0, 0, stage.width, stage.height)
    return viewport if obj._panel is None else viewport.clip(_control_rect(stage, obj._panel))


def _available(stage: Stage, button: Button) -> bool:
    if button._stage is not stage or not button.visible or not button.enabled:
        return False
    parent = button._panel
    return parent is None or (
        parent.visible and bool(_control_rect(stage, button).clip(_clip(stage, button)))
    )
