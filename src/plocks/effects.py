"""Typed graphic effects for Sprite and Puppet appearance."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from .geometry import _number

if TYPE_CHECKING:
    from .puppets import Puppet
    from .sprites import Sprite


class Effect(Enum):
    """Scratch-style graphic effects; zero restores the ordinary appearance.

    COLOR cycles every 200; GHOST is 0..100 percent transparency; BRIGHTNESS
    is -100..100. WHIRL twists in degrees, PIXELATE uses abs(value)/10 pixel
    blocks, MOSAIC repeats copies, and FISHEYE bulges or pinches the picture.
    Effects never alter image assets, bounds, physics, or speech bubbles.
    """

    COLOR = "color"
    FISHEYE = "fisheye"
    WHIRL = "whirl"
    PIXELATE = "pixelate"
    MOSAIC = "mosaic"
    BRIGHTNESS = "brightness"
    GHOST = "ghost"


def _validate(effect: Effect, value: float) -> None:
    if not isinstance(effect, Effect):
        raise TypeError("Use an Effect value, such as Effect.GHOST")
    _number(value, "effect amount")


def _amount(effect: Effect, value: float) -> float:
    if effect is Effect.COLOR:
        return value % 200
    if effect is Effect.GHOST:
        return min(100.0, max(0.0, value))
    if effect is Effect.BRIGHTNESS:
        return min(100.0, max(-100.0, value))
    return value


def _value(actor: Sprite | Puppet, effect: Effect, now: float | None = None) -> float:
    """Borrow a scalar or sample the identical fiber-owned request without storing progress."""
    from ._operations import _EffectRun
    from .motion import _ease

    value = actor._effects.get(effect, 0.0)
    if not isinstance(value, _EffectRun):
        return value
    if now is None:
        now = actor._stage.time if actor._stage is not None else value.started
    progress = (
        1.0
        if not value.seconds or now + 1e-12 >= value.started + value.seconds
        else min(1.0, max(0.0, (now - value.started) / value.seconds))
    )
    t = _ease(progress, value.easing)
    sampled = value.end if t == 1 else (1 - t) * value.start + t * value.end
    return _amount(effect, sampled)
