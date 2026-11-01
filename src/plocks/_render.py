"""Stateless rendering of stage-owned members; all scratch is frame-local."""

from __future__ import annotations

from math import ceil, floor
from typing import TYPE_CHECKING

import pygame

from ._bubbles import _draw_bubble
from .canvas import Canvas
from .geometry import Bounds, Point, _rotate
from .imaging import Image
from .motion import _mirrored, _visual_direction
from .puppets import Puppet
from .rigging import _pivots
from .sprites import Sprite
from .tiling import TiledBackground, TileMap
from .ui import Button, Label, Panel, ProgressBar

if TYPE_CHECKING:
    from .stage import Stage


def _image(
    stage: Stage,
    target: pygame.Surface,
    asset: Image,
    position: Point,
    direction: float,
    scale: float,
    mirrored: bool,
    pixels: pygame.Surface | None = None,
) -> None:
    """Place transformed pixel art by its source anchor; scratch surfaces stay local."""
    _blit(
        target,
        asset._pixels if pixels is None else pixels,
        asset.anchor,
        stage.to_screen(position),
        direction,
        scale,
        mirrored,
    )


def _blit(
    target: pygame.Surface,
    source: pygame.Surface,
    anchor: Point,
    position: Point,
    direction: float,
    scale: float,
    mirrored: bool,
) -> None:
    """Paint source pixels around their anchor at a supplied screen-coordinate point."""
    width, height = source.get_size()
    if mirrored:
        source = pygame.transform.flip(source, True, False)
    scaled = pygame.transform.scale(
        source, (max(1, round(width * scale)), max(1, round(height * scale)))
    )
    image = pygame.transform.rotate(scaled, 90 - direction)
    ax, ay = anchor
    local_x = width / 2 - ax
    dx, dy = _rotate((-local_x if mirrored else local_x, ay - height / 2), direction, scale)
    center = position[0] + dx, position[1] - dy
    target.blit(
        image, (floor(center[0] - image.width / 2 + 0.5), floor(center[1] - image.height / 2 + 0.5))
    )


def _sprite(stage: Stage, target: pygame.Surface, sprite: Sprite) -> None:
    from ._effects import _apply

    _image(
        stage,
        target,
        sprite.image,
        sprite.position,
        _visual_direction(sprite.direction, sprite.rotation_style),
        sprite.scale,
        _mirrored(sprite.direction, sprite.rotation_style),
        _apply(sprite.image._pixels, sprite),
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
            elif isinstance(obj, TiledBackground):
                _background(stage, target, obj)
    for obj in members:
        if isinstance(obj, (Sprite, Puppet)):
            _draw_bubble(stage, target, obj)
    from ._ui import _draw as draw_ui

    for obj in members:
        if isinstance(obj, (Button, Label, ProgressBar, Panel)) and obj.visible:
            draw_ui(stage, target, obj)
    for callback in tuple(stage._draws):
        canvas = Canvas(target, stage)
        try:
            from .stage import _check_callback_result

            _check_callback_result(callback(canvas), "draw")
        finally:
            canvas._surface = None
    from ._alerts import _draw as draw_alert

    draw_alert(stage, target)
    pygame.display.flip()


def _puppet(stage: Stage, target: pygame.Surface, actor: Puppet) -> None:
    from ._effects import _apply, _settings

    if _settings(actor):
        source, anchor = _assembled(actor)
        _blit(
            target,
            _apply(source, actor),
            anchor,
            stage.to_screen(actor.position),
            _visual_direction(actor.direction, actor.rotation_style),
            actor.scale,
            _mirrored(actor.direction, actor.rotation_style),
        )
        return
    pivots = _pivots(actor.pose)
    direction = _visual_direction(actor.direction, actor.rotation_style)
    mirrored = _mirrored(actor.direction, actor.rotation_style)
    for name, image in actor._parts.items():
        (px, py), angle = pivots[name]
        dx, dy = _rotate((-px if mirrored else px, py), direction, actor.scale)
        _image(
            stage,
            target,
            image,
            (actor.x + dx, actor.y + dy),
            direction - angle if mirrored else direction + angle,
            actor.scale,
            mirrored,
        )


def _assembled(actor: Puppet) -> tuple[pygame.Surface, Point]:
    """Compose the current rig once in local coordinates; return pixels and its pivot anchor."""
    pivots = _pivots(actor.pose)
    points: list[Point] = []
    for name, image in actor._parts.items():
        (px, py), angle = pivots[name]
        ax, ay = image.anchor
        for x in (0, image.width):
            for y in (0, image.height):
                dx, dy = _rotate((x - ax, ay - y), angle + 90)
                points.append((px + dx, py + dy))
    left, right = floor(min(x for x, _ in points)), ceil(max(x for x, _ in points))
    bottom, top = floor(min(y for _, y in points)), ceil(max(y for _, y in points))
    source = pygame.Surface((max(1, right - left), max(1, top - bottom)), pygame.SRCALPHA)
    for name, image in actor._parts.items():
        (px, py), angle = pivots[name]
        _blit(source, image._pixels, image.anchor, (px - left, top - py), angle + 90, 1, False)
    return source, (-float(left), float(top))


def _tiles(stage: Stage, target: pygame.Surface, tiles: TileMap) -> None:
    """Cull by visible cells. Scaled images are scratch for this draw call only."""
    if tiles.opacity == 0:
        return
    scaled: dict[str, pygame.Surface] = {}
    width, height = tiles.tile_size
    cx, cy = tuple(
        origin + (camera - origin) * factor
        for origin, camera, factor in zip(tiles.parallax_origin, stage.camera, tiles.parallax)
    )
    viewport = Bounds(
        cx - stage.width / 2, cy - stage.height / 2, cx + stage.width / 2, cy + stage.height / 2
    )
    for row, column in tiles.tiles_touching(viewport, solid_only=False):
        key = tiles.get_tile(row=row, column=column)
        if key is None:
            continue
        if key not in scaled:
            image = pygame.transform.scale(tiles.palette[key]._pixels, tiles.tile_size)
            if tiles.opacity < 1:
                image = image.copy()
                image.set_alpha(round(tiles.opacity * 255))
            scaled[key] = image
        x = stage.width / 2 + tiles.x + column * width - cx
        y = stage.height / 2 - tiles.y + row * height + cy
        target.blit(scaled[key], (round(x), round(y)))


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
    image = background.image
    dx = background.offset[0] - stage.camera[0] * background.parallax[0]
    dy = background.offset[1] - stage.camera[1] * background.parallax[1]
    phase_x = (x % image.width + dx % image.width) % image.width
    phase_y = (y % image.height - dy % image.height) % image.height
    start_x = clip.left - (clip.left - round(phase_x)) % image.width
    start_y = clip.top - (clip.top - round(phase_y)) % image.height
    try:
        for top in range(start_y, clip.bottom, image.height):
            for left in range(start_x, clip.right, image.width):
                target.blit(image._pixels, (left, top))
    finally:
        target.set_clip(previous)
