"""Stateless rendering of stage-owned members; all scratch is frame-local."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from ._bubbles import _draw_bubble
from .canvas import Canvas
from .geometry import Point, _rotate
from .imaging import Costume
from .motion import _mirrored, _visual_direction
from .puppets import Puppet
from .rigging import _pivots
from .sprites import Sprite
from .tiling import TiledBackground, TileMap

if TYPE_CHECKING:
    from .stage import Stage


def _image(
    stage: Stage,
    target: pygame.Surface,
    costume: Costume,
    position: Point,
    direction: float,
    scale: float,
    mirrored: bool,
) -> None:
    """Place transformed pixel art by its source anchor; scratch surfaces stay local."""
    source = pygame.transform.flip(costume._pixels, True, False) if mirrored else costume._pixels
    scaled = pygame.transform.scale(
        source, (max(1, round(costume.width * scale)), max(1, round(costume.height * scale)))
    )
    image = pygame.transform.rotate(scaled, 90 - direction)
    ax, ay = costume.anchor
    local_x = costume.width / 2 - ax
    dx, dy = _rotate((-local_x if mirrored else local_x, ay - costume.height / 2), direction, scale)
    center = stage.to_screen((position[0] + dx, position[1] + dy))
    target.blit(image, image.get_rect(center=(round(center[0]), round(center[1]))))


def _sprite(stage: Stage, target: pygame.Surface, sprite: Sprite) -> None:
    _image(
        stage,
        target,
        sprite.costume,
        sprite.position,
        _visual_direction(sprite.direction, sprite.rotation_style),
        sprite.scale,
        _mirrored(sprite.direction, sprite.rotation_style),
    )


def frame(stage: Stage) -> None:
    """Clear, draw in stable layer order, then invoke overlay callbacks."""
    target = stage._target
    if target is None:
        return
    target.fill(stage.background)
    members = sorted(stage._members, key=lambda member: member.layer)
    for obj in members:
        if obj.visible:
            if isinstance(obj, Sprite):
                _sprite(stage, target, obj)
            elif isinstance(obj, Puppet):
                _puppet(stage, target, obj)
            elif isinstance(obj, TileMap):
                _tiles(stage, target, obj)
            else:
                _background(stage, target, obj)
    for obj in members:
        if isinstance(obj, (Sprite, Puppet)):
            _draw_bubble(stage, target, obj)
    for callback in tuple(stage._draws):
        canvas = Canvas(target, stage)
        try:
            callback(canvas)
        finally:
            canvas._surface = None
    pygame.display.flip()


def _puppet(stage: Stage, target: pygame.Surface, actor: Puppet) -> None:
    pivots = _pivots(actor.pose)
    direction = _visual_direction(actor.direction, actor.rotation_style)
    mirrored = _mirrored(actor.direction, actor.rotation_style)
    for name, costume in actor._parts.items():
        (px, py), angle = pivots[name]
        dx, dy = _rotate((-px if mirrored else px, py), direction, actor.scale)
        _image(
            stage,
            target,
            costume,
            (actor.x + dx, actor.y + dy),
            direction - angle if mirrored else direction + angle,
            actor.scale,
            mirrored,
        )


def _tiles(stage: Stage, target: pygame.Surface, tiles: TileMap) -> None:
    """Cull by visible cells. Scaled images are scratch for this draw call only."""
    scaled: dict[str, pygame.Surface] = {}
    width, height = tiles.tile_size
    for row, column in tiles.tiles_touching(stage.world_bounds, solid_only=False):
        key = tiles.get_tile(row=row, column=column)
        if key is None:
            continue
        if key not in scaled:
            scaled[key] = pygame.transform.scale(tiles.palette[key]._pixels, tiles.tile_size)
        position = stage.to_screen((tiles.x + column * width, tiles.y - row * height))
        target.blit(scaled[key], (round(position[0]), round(position[1])))


def _background(stage: Stage, target: pygame.Surface, background: TiledBackground) -> None:
    """Repeat into a temporary clip, restoring the render target before overlays."""
    area = background.area or stage.bounds
    x, y = stage.to_screen((area.left, area.top), world=False)
    previous = target.get_clip()
    viewport = stage.bounds
    left, right = max(area.left, viewport.left), min(area.right, viewport.right)
    bottom, top = max(area.bottom, viewport.bottom), min(area.top, viewport.top)
    if left >= right or bottom >= top:
        return
    clip_x, clip_y = stage.to_screen((left, top), world=False)
    clip = previous.clip(
        pygame.Rect(round(clip_x), round(clip_y), round(right - left), round(top - bottom))
    )
    if clip.width == 0 or clip.height == 0:
        return
    target.set_clip(clip)
    costume = background.costume
    dx, dy = background.offset
    phase_x = (x % costume.width + dx % costume.width) % costume.width
    phase_y = (y % costume.height - dy % costume.height) % costume.height
    start_x = clip.left - (clip.left - round(phase_x)) % costume.width
    start_y = clip.top - (clip.top - round(phase_y)) % costume.height
    try:
        for top in range(start_y, clip.bottom, costume.height):
            for left in range(start_x, clip.right, costume.width):
                target.blit(costume._pixels, (left, top))
    finally:
        target.set_clip(previous)
