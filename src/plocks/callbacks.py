"""Synchronous function contracts; callbacks need no wrapper objects."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._commands import Actor
    from .actions import Action
    from .canvas import Canvas
    from .events import Event
    from .scripts import Script
    from .stage import Stage

type Callback[D] = Callable[[Event[Stage, D]], None | Action]
type ActorCallback[T: Actor, D] = Callable[[Event[T, D]], None | Action | Script[T] | Script[Actor]]
type UpdateCallback = Callable[[Event[Stage, float]], None]
type ActorUpdateCallback[T: Actor] = Callable[[Event[T, float]], None]
type DrawCallback = Callable[[Canvas], None]
