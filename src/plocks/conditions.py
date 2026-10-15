"""Boolean tests evaluated when a behavior reaches them."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

from .errors import StageError
from .input import Key
from .puppets import Puppet
from .sprites import Sprite
from .tiling import TileMap

Target_contra = TypeVar("Target_contra", bound=Sprite | Puppet, contravariant=True)


class Condition(ABC, Generic[Target_contra]):  # noqa: UP046 -- explicit contravariance is contractual
    """A typed immediate boolean test; it does not subscribe or retain results."""

    __slots__ = ()

    @abstractmethod
    def test(self, actor: Target_contra) -> bool:
        """Evaluate against the actor's current state."""


@dataclass(frozen=True, slots=True)
class KeyDown(Condition[Sprite | Puppet]):
    """True while the actor's stage holds this key; requires membership."""

    key: Key

    def test(self, actor: Sprite | Puppet) -> bool:
        """Read current held input; detached actors raise StageError."""
        if actor._stage is None:
            raise StageError("KeyDown requires stage membership")
        return actor._stage.keyboard.is_down(self.key)


@dataclass(frozen=True, slots=True)
class Touching(Condition[Sprite | Puppet]):
    """Test current AABB or solid-tile overlap, independent of visibility."""

    other: Sprite | Puppet | TileMap

    def test(self, actor: Sprite | Puppet) -> bool:
        """Evaluate overlap now, without moving either object."""
        return actor.touching(self.other)
