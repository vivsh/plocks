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
    from .tiling import TileMap
    from .ui import Button

_R_co = TypeVar("_R_co", bound="Stage | Sprite | Puppet | Button", covariant=True)
_D_co = TypeVar("_D_co", covariant=True)


@dataclass(frozen=True, slots=True)
class Event(Generic[_R_co, _D_co]):  # noqa: UP046 -- explicit receiver and payload types preserve callback checking
    """One callback occurrence: source, receiving target, and typed data.

    Startup and clone start/end data are None. Button data is GamepadPress or
    GamepadRelease; click data is (position, button). Update data is simulated
    seconds, periodic data is the configured interval, hit data is Collision, and
    edge data is frozenset[Edge] with all currently reached rectangle sides.
    Broadcast data has its Message payload type
    and is passed by reference. Engine sources are Stage; broadcast sources are
    their senders. Clone-start sources are the copied actors and targets are their
    new clones. Targets retain their exact Sprite/Puppet/Stage type for editor
    completion. Each receiver gets an immutable envelope with no execution history.
    The Message channel is selected by registration, not stored on this occurrence.
    """

    source: Stage | Sprite | Puppet
    target: _R_co
    data: _D_co


@dataclass(frozen=True, slots=True)
class Collision:
    """One physical contact: the other owner, world contact point and outward normal.

    Used as on_hit Event.data. target is the other Sprite/Puppet/TileMap; the
    Event.target is the receiving actor. normal points out of the other surface
    towards the receiver. cell is (row, column) for a tile, otherwise None.
    Values are immutable snapshots; later motion or edits do not update them.
    """

    target: Sprite | Puppet | TileMap
    point: Point
    normal: Point
    cell: tuple[int, int] | None


type Click = tuple[Point, MouseButton]


@dataclass(frozen=True, slots=True)
class GamepadPress:
    """A logical button press (or turbo repeat), identifying its stable player slot.

    Used as Event.data. Engine Event.source remains Stage, and Event.target is
    the receiver. The gamepad is borrowed; no hardware snapshot is copied here.
    """

    gamepad: Gamepad
    button: GamepadButton


@dataclass(frozen=True, slots=True)
class GamepadRelease:
    """A logical button release; gamepad identifies the player and button the control."""

    gamepad: Gamepad
    button: GamepadButton
