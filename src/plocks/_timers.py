"""Periodic registrations borrow drivers from the existing simulation runner."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ._operations import _context, _Delay, _suspend
from ._scripts import WhenBusy
from .errors import StageError
from .geometry import _number, _positive

if TYPE_CHECKING:
    from ._commands import Actor
    from ._scripts import _Handler
    from .actions import Action
    from .stage import Stage


@dataclass(eq=False, slots=True)
class _Timer:
    handler: _Handler
    seconds: float
    action: Action | None = None


def _interval(seconds: float, when_busy: WhenBusy) -> float:
    """Validate decorator settings before returning or installing a callback."""
    seconds = _positive(seconds, "seconds")
    if not isinstance(when_busy, WhenBusy):
        raise TypeError("Use WhenBusy.IGNORE or RESTART")
    return seconds


def _start(stage: Stage, timer: _Timer) -> None:
    """Admit a fresh stage-owned driver; the coroutine owns its only deadline."""
    from ._scripts import _admit

    deadline = _number(stage.time + timer.seconds, "repeat deadline")
    timer.action = _admit(stage, _repeat_event(stage, timer, deadline), None)


def _register(stage: Stage, handler: _Handler, seconds: float) -> None:
    """Commit a definition only after its existing execution budget accepts it."""
    if len(stage._timers) >= 1024:
        raise StageError("A stage supports at most 1024 periodic registrations")
    timer = _Timer(handler, seconds)
    _start(stage, timer)
    stage._timers.append(timer)


async def _repeat_event(stage: Stage, timer: _Timer, deadline: float) -> None:
    """Keep the phase-aligned deadline local; never replay missed sub-tick events."""
    from ._scripts import _trigger

    _, driver, _, _ = await _context()
    try:
        while stage.running and timer.action is driver:
            await _suspend(_Delay(deadline))
            if not stage.running or timer.action is not driver:
                return
            _trigger(stage, timer.handler, timer.seconds)
            if not stage.running or timer.action is not driver:
                return
            remaining = timer.seconds - (max(0.0, stage.time - deadline) % timer.seconds)
            deadline = _number(stage.time + remaining, "repeat deadline")
            if deadline <= stage.time + 1e-12:
                deadline = _number(stage.time + 1 / stage.tick_rate, "repeat deadline")
    finally:
        if timer.action is driver:
            timer.action = None


def _stop(timer: _Timer) -> None:
    """Clear the inverse link before cancellation can run coroutine cleanup."""
    driver = timer.action
    timer.action = None
    if driver is not None:
        driver.cancel()


def _detach(stage: Stage, actor: Actor) -> None:
    """Stop one receiver's drivers immediately, retaining ordinary definitions."""
    errors: list[BaseException] = []
    for timer in tuple(stage._timers):
        if timer.handler.actor is actor:
            try:
                _stop(timer)
            except BaseException as error:  # noqa: BLE001 -- cancel every driver before reporting failure
                errors.append(error)
    if errors:
        raise errors[0]


def _check_attach(stage: Stage, actor: Actor) -> None:
    """Check the existing execution budget before acquiring attachment resources."""
    from ._scripts import _count

    needed = sum(timer.handler.actor is actor for timer in stage._timers)
    if _count(stage) + needed > 128:
        raise StageError("Cannot restart periodic callbacks: 128-execution limit reached")


def _resume(stage: Stage, actor: Actor) -> None:
    """Start fresh intervals on re-add, rolling back every partially admitted driver."""
    started: list[_Timer] = []
    try:
        for timer in tuple(stage._timers):
            if timer.handler.actor is actor:
                _start(stage, timer)
                started.append(timer)
    except BaseException as error:
        for timer in started:
            try:
                _stop(timer)
            except BaseException as cleanup:  # noqa: BLE001 -- preserve the admission failure
                error.add_note(f"Timer restart rollback also failed: {cleanup!r}")
        raise


def _inherit(stage: Stage, source: Actor, inherited: Callable[[_Handler], _Handler]) -> None:
    """Snapshot receiver definitions; clone rollback owns pruning partial copies."""
    from ._scripts import _count

    definitions = tuple(timer for timer in stage._timers if timer.handler.actor is source)
    if len(stage._timers) + len(definitions) > 1024:
        raise StageError("A stage supports at most 1024 periodic registrations")
    if _count(stage) + len(definitions) > 128:
        raise StageError("Cannot inherit periodic callbacks: 128-execution limit reached")
    for timer in definitions:
        _register(stage, inherited(timer.handler), timer.seconds)


def _forget(stage: Stage, actor: Actor) -> None:
    """Prune a removed/failed clone's definitions even if cancellation fails."""
    try:
        _detach(stage, actor)
    finally:
        stage._timers[:] = [timer for timer in stage._timers if timer.handler.actor is not actor]
