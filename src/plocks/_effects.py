"""Stateless effect execution and operation-local raster transformations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from .effects import Effect, _amount, _value
from .errors import StageError
from .geometry import _number
from .motion import Ease

if TYPE_CHECKING:
    from .puppets import Puppet
    from .sprites import Sprite


async def _write(actor: Sprite | Puppet, effect: Effect, value: float, *, change: bool) -> None:
    from ._operations import _context
    from ._scripts import _conflicts

    stage, root, _, _ = await _context()
    if actor._stage is not stage:
        raise StageError("Effects require membership in the executing stage")
    amount = _number(value + (_value(actor, effect) if change else 0), "effect amount")
    _conflicts(actor, False, False, root, effect=effect)
    if actor._stage is not stage:
        raise StageError("Effect target was detached during cancellation cleanup")
    if change:
        amount = _number(_value(actor, effect) + value, "effect amount")
    actor._effects[effect] = _amount(effect, amount)


async def _clear(actor: Sprite | Puppet) -> None:
    from ._operations import _context
    from ._scripts import _conflicts

    stage, root, _, _ = await _context()
    if actor._stage is not stage:
        raise StageError("Effects require membership in the executing stage")
    _conflicts(actor, False, False, root, all_effects=True)
    if actor._stage is not stage:
        raise StageError("Effect target was detached during cancellation cleanup")
    actor._effects.clear()


async def _animate(
    actor: Sprite | Puppet, effect: Effect, to: float, seconds: float, easing: Ease
) -> None:
    from ._operations import _context, _Delay, _EffectRun, _suspend
    from ._scripts import _conflicts

    stage, root, _, at = await _context()
    if actor._stage is not stage:
        raise StageError("Effects require membership in the executing stage")
    _number(at + seconds, "effect deadline")
    # Keep an unwrapped color destination: 0 -> 200 authors a full hue cycle.
    end = to if effect is Effect.COLOR else _amount(effect, to)
    _conflicts(actor, False, False, root, effect=effect)
    if actor._stage is not stage:
        raise StageError("Effect target was detached during cancellation cleanup")
    operation = _EffectRun(actor, effect, _value(actor, effect), end, at, seconds, easing)
    actor._effects[effect] = operation
    if seconds == 0:
        actor._effects[effect] = _amount(effect, end)
        await _suspend(_Delay(_number(stage.time + 1 / stage.tick_rate, "effect deadline")))
    else:
        await _suspend(operation)


def _settings(actor: Sprite | Puppet) -> dict[Effect, float]:
    """Normalize only this draw's values; an empty result keeps the original fast path."""
    result: dict[Effect, float] = {}
    for effect in actor._effects:
        value = _value(actor, effect)
        if effect is Effect.PIXELATE:
            value = abs(value) / 10
            if value <= 1:
                continue
        elif effect is Effect.MOSAIC:
            value = float(min(512, max(1, round((abs(value) + 10) / 10))))
            if value == 1:
                continue
        elif effect is Effect.FISHEYE:
            value = max(0.0, 1 + value / 100)
            if value == 1:
                continue
        if value or effect is Effect.FISHEYE:
            result[effect] = value
    return result


def _grid(source: pygame.Surface, mosaic: float, block: float) -> pygame.Surface:
    """Sample separable mosaic/pixel blocks using draw-local one-dimensional coordinates."""
    from math import floor

    width, height = source.get_size()
    axes: list[tuple[int, ...]] = []
    for size in (width, height):
        step = min(block, size)
        coordinates: list[int] = []
        for index in range(size):
            unit = ((index + 0.5) / size * mosaic) % 1
            if step:
                unit = (floor(unit * size / step) + 0.5) * step / size
            # Match the centered-coordinate rounding used by the radial sampler.
            centered = unit - 0.5
            coordinates.append(min(size - 1, max(0, floor((centered + 0.5) * size))))
        axes.append(tuple(coordinates))
    original = pygame.image.tobytes(source, "RGBA")
    rows: list[bytes] = []
    for y in axes[1]:
        start = y * width * 4
        rows.append(b"".join(original[start + x * 4 : start + x * 4 + 4] for x in axes[0]))
    return pygame.image.frombytes(b"".join(rows), (width, height), "RGBA")


def _warp(source: pygame.Surface, values: dict[Effect, float]) -> pygame.Surface:
    """Sample nearest source pixels through the fixed mosaic/pixelate/whirl/fisheye map."""
    from math import cos, floor, hypot, radians, sin

    mosaic = values.get(Effect.MOSAIC, 1.0)
    block = values.get(Effect.PIXELATE, 0.0)
    if Effect.WHIRL not in values and Effect.FISHEYE not in values:
        return _grid(source, mosaic, block)
    width, height = source.get_size()
    original = pygame.image.tobytes(source, "RGBA")
    pixels = bytearray(len(original))
    block_x, block_y = min(block, width), min(block, height)
    whirl = radians(values.get(Effect.WHIRL, 0.0))
    power = values.get(Effect.FISHEYE, 1.0)
    for y in range(height):
        for x in range(width):
            u, v = ((x + 0.5) / width * mosaic) % 1, ((y + 0.5) / height * mosaic) % 1
            if block:
                u = (floor(u * width / block_x) + 0.5) * block_x / width
                v = (floor(v * height / block_y) + 0.5) * block_y / height
            cx, cy = u - 0.5, v - 0.5
            if whirl:
                angle = -whirl * max(0.0, 1 - hypot(cx, cy) * 2) ** 2
                cosine, sine = cos(angle), sin(angle)
                cx, cy = cx * cosine - cy * sine, cx * sine + cy * cosine
            if power != 1:
                radius = hypot(cx * 2, cy * 2)
                if radius:
                    factor = min(radius, 1.0) ** power * max(1.0, radius) / radius
                    cx, cy = cx * factor, cy * factor
            sx = min(width - 1, max(0, floor((cx + 0.5) * width)))
            sy = min(height - 1, max(0, floor((cy + 0.5) * height)))
            start, end = (sy * width + sx) * 4, (y * width + x) * 4
            pixels[end : end + 4] = original[start : start + 4]
    return pygame.image.frombytes(bytes(pixels), (width, height), "RGBA")


def _colors(source: pygame.Surface, color: float, brightness: float) -> pygame.Surface:
    """Apply hue and brightness in Pillow's C-backed operations, preserving per-pixel alpha."""
    from PIL import Image as PillowImage
    from PIL import ImageChops

    image = PillowImage.frombytes("RGBA", source.get_size(), pygame.image.tobytes(source, "RGBA"))
    alpha = image.getchannel("A")
    rgb = image.convert("RGB")
    if color:
        hue, saturation, value = rgb.convert("HSV").split()
        shift = round(color * 256 / 200)
        hue = ImageChops.add_modulo(hue, PillowImage.new("L", hue.size, shift % 256))
        rgb = PillowImage.merge("HSV", (hue, saturation, value)).convert("RGB")
    if brightness:
        amount = round(brightness * 255 / 100)
        adjustment = PillowImage.new("RGB", rgb.size, (abs(amount),) * 3)
        rgb = (
            ImageChops.add(rgb, adjustment) if amount > 0 else ImageChops.subtract(rgb, adjustment)
        )
    rgb.putalpha(alpha)
    return pygame.image.frombytes(rgb.tobytes(), source.get_size(), "RGBA")


def _apply(source: pygame.Surface, actor: Sprite | Puppet) -> pygame.Surface:
    """Return operation-local working pixels; original asset pixels are never mutated."""
    values = _settings(actor)
    if not values:
        return source
    warped = any(
        effect in values
        for effect in (Effect.MOSAIC, Effect.PIXELATE, Effect.WHIRL, Effect.FISHEYE)
    )
    result = _warp(source, values) if warped else source
    color, brightness = values.get(Effect.COLOR, 0.0), values.get(Effect.BRIGHTNESS, 0.0)
    if color or brightness:
        result = _colors(result, color, brightness)
    ghost = values.get(Effect.GHOST, 0.0)
    if ghost:
        if result is source:
            result = result.copy()
        result.fill(
            (255, 255, 255, round(255 * (1 - ghost / 100))), special_flags=pygame.BLEND_RGBA_MULT
        )
    return result
