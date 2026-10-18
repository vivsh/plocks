"""Actor dialogue; fonts, layout, measurements and surfaces live only during a draw."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pygame

from ._operations import _BubbleRun

if TYPE_CHECKING:
    from ._commands import _Say, _Think
    from .geometry import Point
    from .puppets import Puppet
    from .sprites import Sprite
    from .stage import Stage


def _validate_text(text: str) -> None:
    if not isinstance(text, str):
        raise TypeError("Bubble text must be a str; use str(value) or an f-string")
    if any((ord(c) < 32 and c not in "\t\n\r") or ord(c) == 127 for c in text):
        raise ValueError("Bubble text cannot contain control characters except tab and newline")


def _set_bubble(actor: Sprite | Puppet, definition: _Say | _Think | None) -> None:
    from ._scripts import _conflicts

    _conflicts(actor, False, False, bubble=True)
    actor._bubble = definition if definition is not None and definition.text.strip() else None


def _characters(text: str) -> Iterator[str]:
    """Normalize only the consumed prefix, without copying the whole input string."""
    previous_cr = False
    for char in text:
        if char == "\n" and previous_cr:
            previous_cr = False
            continue
        previous_cr = char == "\r"
        if char in "\r\n":
            yield "\n"
        elif char == "\t":
            yield from "    "
        else:
            yield char


def _lines(font: pygame.font.Font, text: str, width: int) -> Iterator[str]:
    """Wrap lazily at spaces or split long words; never render an unbounded word."""
    line = ""
    for char in _characters(text):
        if char == "\n":
            yield line.rstrip()
            line = ""
            continue
        if font.size(line + char)[0] <= width:
            line += char
            continue
        space = line.rfind(" ")
        if space > 0 and char != " ":
            yield line[:space].rstrip()
            line = line[space + 1 :] + char
        else:
            if line:
                yield line.rstrip()
            line = char if char != " " else ""
        if font.size(line)[0] > width:
            # Even a single glyph cannot fit: omit that unreadable fragment.
            return
    yield line.rstrip()


def _ellipsis(font: pygame.font.Font, line: str, width: int) -> str:
    if font.size("...")[0] > width:
        return ""
    line = line.rstrip()
    while line and font.size(line + "...")[0] > width:
        line = line[:-1].rstrip()
    return line + "..."


def _wrap_text(font: pygame.font.Font, text: str, width: int, limit: int) -> tuple[str, ...]:
    """Keep only visible lines and one look-ahead line to detect truncation."""
    if width <= 0 or limit <= 0:
        return ()
    result: list[str] = []
    for line in _lines(font, text, width):
        if len(result) == limit:
            result[-1] = _ellipsis(font, result[-1], width)
            break
        result.append(line)
    return tuple(result)


def _layout(
    stage: Stage, actor: Sprite | Puppet, font: pygame.font.Font, text: str
) -> tuple[pygame.Rect, tuple[str, ...], Point] | None:
    """Place measured text near visible actor bounds, accepting overlap as a last resort."""
    bounds, view = actor.bounds, stage.world_bounds
    if not bounds.intersects(view):
        return None
    left, top = stage.to_screen((max(bounds.left, view.left), min(bounds.top, view.top)))
    right, bottom = stage.to_screen(
        (min(bounds.right, view.right), max(bounds.bottom, view.bottom))
    )
    width = min(stage.width - 16, max(240, 10 * stage.bubble_text_size))
    stride = max(font.get_linesize(), stage.bubble_text_size)
    limit = (stage.height - 32) // stride
    lines = _wrap_text(font, text, width - 16, limit)
    if not lines:
        return None
    height = len(lines) * stride + 16
    above, below = max(0, int(top - 20)), max(0, int(stage.height - bottom - 20))
    on_top = height <= above or (height > below and above >= below)
    room = above if on_top else below
    if height > room >= stride + 16:
        count = (room - 16) // stride
        lines = (*lines[: count - 1], _ellipsis(font, lines[count - 1], width - 16))
        height = len(lines) * stride + 16
    body_width = max(font.size(line)[0] for line in lines) + 16
    center = (left + right) / 2
    x = max(8, min(stage.width - 8 - body_width, round(center - body_width / 2)))
    y = round(top - 12 - height) if on_top else round(bottom + 12)
    y = max(8, min(stage.height - 8 - height, y))
    return pygame.Rect(x, y, body_width, height), lines, (center, top if on_top else bottom)


def _connector(target: pygame.Surface, body: pygame.Rect, tip: Point, thought: bool) -> None:
    """Attach a small pointer or circle chain without drawing through the body."""
    if body.collidepoint(tip):
        return
    y = body.bottom if tip[1] >= body.bottom else body.top
    if not (tip[1] >= body.bottom or tip[1] <= body.top):
        return
    x = max(body.left + min(10, body.width / 2), min(body.right - min(10, body.width / 2), tip[0]))
    distance = abs(tip[1] - y)
    if distance < 2:
        return
    if thought:
        for fraction, radius in ((0.2, 4), (0.55, 3), (0.85, 2)):
            center = (round(x + (tip[0] - x) * fraction), round(y + (tip[1] - y) * fraction))
            radius = max(1, min(radius, int(distance / 3)))
            pygame.draw.circle(target, "#202020", center, radius)
            if radius > 1:
                pygame.draw.circle(target, "white", center, radius - 1)
    else:
        half = min(6, body.width / 2)
        points = ((x - half, y), (x + half, y), tip)
        pygame.draw.polygon(target, "white", points)
        pygame.draw.lines(target, "#202020", False, (points[0], tip, points[1]), 2)


def _draw_bubble(stage: Stage, target: pygame.Surface, actor: Sprite | Puppet) -> None:
    """Paint dialogue between scene and Canvas overlays, using the bundled font."""
    from ._commands import _Think

    source = actor._bubble
    if source is None or not actor.visible or not actor.bounds.intersects(stage.world_bounds):
        return
    if stage.bubble_text_size + 32 > stage.height or stage.width <= 32:
        return
    definition = source.definition if isinstance(source, _BubbleRun) else source
    if not pygame.font.get_init():
        pygame.font.init()
    font = pygame.font.Font(None, stage.bubble_text_size)
    layout = _layout(stage, actor, font, definition.text)
    if layout is None:
        return
    body, lines, tip = layout
    previous = target.get_clip()
    target.set_clip(previous.clip(target.get_rect()))
    try:
        _connector(target, body, tip, isinstance(definition, _Think))
        pygame.draw.rect(target, "white", body, border_radius=10)
        pygame.draw.rect(target, "#202020", body, width=2, border_radius=10)
        stride = max(font.get_linesize(), stage.bubble_text_size)
        for row, line in enumerate(lines):
            target.blit(font.render(line, True, "#202020"), (body.x + 8, body.y + 8 + row * stride))
    finally:
        target.set_clip(previous)
