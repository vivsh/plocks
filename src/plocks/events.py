"""Immutable callback occurrences with precisely typed receivers and payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

from .gamepads import GamepadButton
from .geometry import Point
from .input import MouseButton

if TYPE_CHECKING:
    from .gamepads import Gamepad
    from .puppets import Puppet
    from .sprites import Sprite
    from .stage import Stage

_R_co = TypeVar("_R_co", bound="Stage | Sprite | Puppet", covariant=True)
_D = TypeVar("_D")


@dataclass(frozen=True, slots=True)
class Event(Generic[_R_co, _D]):  # noqa: UP046 -- explicit receiver and payload types preserve callback checking
    """One callback occurrence: source, receiving target, and typed data.

    Startup and clone-start data are None; key data is Key, click data is
    (position, button), and
    update data is simulated seconds. Broadcast data has its Message payload type
    and is passed by reference. Engine sources are Stage; broadcast sources are
    their senders. Clone-start sources are the copied actors and targets are their
    new clones. Targets retain their exact Sprite/Puppet/Stage type for editor
    completion. Each receiver gets an immutable envelope with no execution history.
    The Message channel is selected by registration, not stored on this occurrence.
    """

    source: Stage | Sprite | Puppet
    target: _R_co
    data: _D


type Click = tuple[Point, MouseButton]


@dataclass(frozen=True, slots=True)
class RemoteChange:
    """A zero-based remote slot became ready or disconnected, with a safe reason."""

    slot: int
    connected: bool
    reason: str | None


@dataclass(frozen=True, slots=True)
class GamepadPress:
    """A logical button press (or turbo repeat), identifying its stable player slot.

    Used as Event.data. Engine Event.source remains Stage, and Event.target is
    the receiver. The gamepad is borrowed; no hardware snapshot is copied here.
    """

    gamepad: Gamepad
    button: GamepadButton
