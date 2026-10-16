"""Scheduled executions: calling admits work; awaiting observes that same work."""

from __future__ import annotations

from collections.abc import Coroutine, Generator
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Self

from .errors import ActionCancelled

if TYPE_CHECKING:
    from ._scripts import _Fiber, _Handler
    from .puppets import Puppet
    from .sprites import Sprite
    from .stage import Stage


class _Outcome(Enum):
    SUCCESS = "success"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class _Queued:
    work: Coroutine[object, object, None]
    admitted_at: float


@dataclass(frozen=True, slots=True)
class _Completion:
    at: float
    result: _Outcome | BaseException


class Action:
    """One stage-owned execution returned by a command; do not construct directly.

    Calling a command schedules it even if you discard this value. Use ``after``
    to sequence commands, ``cancel()`` to stop one, or await it in an advanced
    Plocks callback. Cancellation never rewinds movement or runs remaining steps.
    """

    __slots__ = ("_actor", "_after", "_handler", "_parent", "_stage", "_state")
    _stage: Stage
    _actor: Sprite | Puppet | None
    _after: Action | None
    _parent: _Fiber | None
    _handler: _Handler | None
    _state: _Queued | _Fiber | _Completion

    def __new__(cls) -> Self:
        raise TypeError("Actions are returned by Plocks commands, not constructed directly")

    @property
    def done(self) -> bool:
        """Whether this execution succeeded, was canceled, or failed."""
        return isinstance(self._state, _Completion)

    @property
    def cancelled(self) -> bool:
        """Whether cancellation ended this execution, including dependency cancellation."""
        return isinstance(self._state, _Completion) and self._state.result is _Outcome.CANCELLED

    @property
    def exception(self) -> BaseException | None:
        """Original failure, or None. Failures also stop and report through the stage."""
        state = self._state
        return (
            state.result
            if isinstance(state, _Completion) and isinstance(state.result, BaseException)
            else None
        )

    def cancel(self) -> None:
        """Cancel this execution and its structured children; repeated calls are harmless."""
        from ._scripts import _cancel

        _cancel(self._stage, self)

    def __await__(self) -> Generator[object, object, None]:
        """Observe this execution in a Plocks coroutine; no new execution is created."""
        from ._operations import _AwaitAction

        yield _AwaitAction(self)
        if self.cancelled:
            raise ActionCancelled("The awaited action was canceled")
        if self.exception is not None:
            raise self.exception
