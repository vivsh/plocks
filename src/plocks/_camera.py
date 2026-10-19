"""Camera-follow configuration and operation-local viewport calculations."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import TYPE_CHECKING

from .geometry import Bounds, Point, _point

if TYPE_CHECKING:
    from ._commands import Actor
    from .stage import Stage


@dataclass(frozen=True, slots=True)
class _CameraFollow:
    actor: Actor
    offset: Point
    bounds: Bounds | None
    smoothing: float


def _clamp(stage: Stage, point: Point, bounds: Bounds | None) -> Point:
    x, y = point
    if bounds is not None:
        b = bounds
        x = (
            b.left / 2 + b.right / 2
            if b.width < stage.width
            else max(b.left + stage.width / 2, min(b.right - stage.width / 2, x))
        )
        y = (
            b.bottom / 2 + b.top / 2
            if b.height < stage.height
            else max(b.bottom + stage.height / 2, min(b.top - stage.height / 2, y))
        )
    return _point((x, y), "camera target")


def _target(stage: Stage, follow: _CameraFollow) -> Point:
    point = _point((follow.actor.x + follow.offset[0], follow.actor.y + follow.offset[1]))
    return _clamp(stage, point, follow.bounds)


def _sample(stage: Stage, dt: float, *, initial: bool = False) -> None:
    """Use the existing camera position as the sole smoothing progress."""
    follow = stage._camera_follow
    if follow is None or (stage.paused and not initial):
        return
    if follow.actor._stage is not stage:
        stage._camera_follow = None
        return
    x, y = _target(stage, follow)
    if initial or follow.smoothing == 0:
        stage._camera = (x, y)
    else:
        amount = 1 - exp(-dt / follow.smoothing)
        cx, cy = stage.camera
        point = _point(((1 - amount) * cx + amount * x, (1 - amount) * cy + amount * y), "camera")
        stage._camera = _clamp(stage, point, follow.bounds)
