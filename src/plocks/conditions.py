"""Small immutable tests sampled when a Script reaches a branch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .errors import StageError
from .gamepads import Gamepad, GamepadButton
from .input import Key

if TYPE_CHECKING:
    from ._commands import Actor
    from .tiling import TileMap


@dataclass(frozen=True, slots=True)
class KeyDown:
    """Test whether a key is held at branch execution, not at construction."""

    key: Key

    def __post_init__(self) -> None:
        if not isinstance(self.key, Key):
            raise TypeError("KeyDown requires a Key")


@dataclass(frozen=True, slots=True)
class GamepadDown:
    """Test a slot's combined held button when a Script reaches this condition."""

    button: GamepadButton
    gamepad: Gamepad

    def __post_init__(self) -> None:
        if not isinstance(self.button, GamepadButton) or not isinstance(self.gamepad, Gamepad):
            raise TypeError("GamepadDown requires a GamepadButton and stage.gamepads slot")


@dataclass(frozen=True, slots=True)
class Touching:
    """Test current visual bounds/solid tiles; a detached reference is false."""

    other: Actor | TileMap

    def __post_init__(self) -> None:
        from .puppets import Puppet
        from .sprites import Sprite
        from .tiling import TileMap

        if not isinstance(self.other, (Sprite, Puppet, TileMap)):
            raise TypeError("Touching requires an actor or TileMap")


@dataclass(frozen=True, slots=True)
class Grounded:
    """Test physical support; requires the executing actor's physical body."""


@dataclass(frozen=True, slots=True)
class Not:
    """Negate one immutable runtime condition."""

    condition: Condition

    def __post_init__(self) -> None:
        _validate(self.condition)


type Condition = KeyDown | GamepadDown | Touching | Grounded | Not


def _validate(condition: object) -> None:
    depth = 0
    while isinstance(condition, Not):
        depth += 1
        if depth >= 32:
            raise ValueError("Conditions allow at most 32 nesting levels")
        condition = condition.condition
    if not isinstance(condition, (KeyDown, GamepadDown, Touching, Grounded)):
        raise TypeError("Use a runtime Condition, not a bool or function")


def _test(condition: Condition, actor: Actor) -> bool:
    stage = actor._stage
    if stage is None:
        raise StageError("Branch target must belong to its executing stage")
    if isinstance(condition, Not):
        return not _test(condition.condition, actor)
    if isinstance(condition, KeyDown):
        return stage.keyboard.is_down(condition.key)
    if isinstance(condition, GamepadDown):
        if condition.gamepad._stage is not stage:
            raise StageError("GamepadDown must use a slot belonging to the executing stage")
        return condition.gamepad.is_down(condition.button)
    if isinstance(condition, Grounded):
        return actor.body.grounded
    other = condition.other
    if other._stage is None:
        return False
    if other._stage is not stage:
        raise StageError("Touching target belongs to another stage")
    return actor.touching(other)
