"""Transient stage-coordinate drawing above the scene, for overlays and scores."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pygame

from .errors import AssetError, StageError
from .geometry import Bounds, Color, Point, _integer, _positive

if TYPE_CHECKING:
    from .stage import Stage


class Canvas:
    """A callback-scoped drawing target. Do not retain it after on_draw returns."""

    __slots__ = ("_stage", "_surface")

    def __init__(self, surface: pygame.Surface, stage: Stage) -> None:
        self._surface: pygame.Surface | None = surface
        self._stage = stage

    def _target(self) -> pygame.Surface:
        if self._surface is None:
            raise StageError("Canvas is valid only during its on_draw callback")
        return self._surface

    def line(self, start: Point, end: Point, *, color: Color = "white", width: int = 1) -> None:
        """Draw a stage-coordinate line of positive integer pixel width."""
        pygame.draw.line(
            self._target(),
            color,
            self._stage.to_screen(start, world=False),
            self._stage.to_screen(end, world=False),
            _integer(width, "width", minimum=1),
        )

    def circle(
        self, center: Point, radius: float, *, color: Color = "white", width: int = 0
    ) -> None:
        """Draw a circle. width=0 fills it; positive width draws an outline."""
        pygame.draw.circle(
            self._target(),
            color,
            self._stage.to_screen(center, world=False),
            _positive(radius, "radius"),
            _integer(width, "width", minimum=0),
        )

    def rectangle(self, bounds: Bounds, *, color: Color = "white", width: int = 0) -> None:
        """Draw stage bounds, filled by default or outlined with positive width."""
        x, y = self._stage.to_screen((bounds.left, bounds.top), world=False)
        pygame.draw.rect(
            self._target(),
            color,
            (x, y, bounds.width, bounds.height),
            _integer(width, "width", minimum=0),
        )

    def text(
        self,
        text: str,
        position: Point,
        *,
        size: int = 24,
        color: Color = "white",
        font: str | Path | None = None,
    ) -> None:
        """Draw text with its top-left at position. Optional fonts are project TTF files."""
        target = self._target()
        _integer(size, "size", minimum=1)
        if not pygame.font.get_init():
            pygame.font.init()
        try:
            face = pygame.font.Font(str(font) if font is not None else None, size)
            image = face.render(text, False, color)
        except (OSError, pygame.error) as error:
            raise AssetError(f"Cannot draw font {font}: {error}") from error
        target.blit(image, self._stage.to_screen(position, world=False))
