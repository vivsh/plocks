"""Periodic events driven by the existing Action coroutine and simulation clock."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._operations import _context, _Delay, _suspend
from .geometry import _number

if TYPE_CHECKING:
    from ._scripts import _Handler
    from .stage import Stage


async def _repeat_event(stage: Stage, seconds: float, handler: _Handler, deadline: float) -> None:
    """Keep one phase-aligned deadline in the coroutine, not a second timer registry."""
    from ._scripts import _trigger

    await _context()
    while stage.running:
        await _suspend(_Delay(deadline))
        if stage.running:
            _trigger(stage, handler, seconds)
        # Sub-tick intervals cannot create an unbounded catch-up loop.
        remaining = seconds - (max(0.0, stage.time - deadline) % seconds)
        deadline = _number(stage.time + remaining, "repeat deadline")
        if deadline <= stage.time + 1e-12:
            deadline = _number(stage.time + 1 / stage.tick_rate, "repeat deadline")
