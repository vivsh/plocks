"""Typed physical links owned by one world; create them through stage.physics."""

from __future__ import annotations

from math import degrees, radians
from typing import TYPE_CHECKING, Self, cast

from .geometry import Point, _number, _positive

if TYPE_CHECKING:
    from pymunk import constraints

    from ._commands import Actor
    from .physics import Physics


class Connection:
    """A world-owned physical link. Factory calls attach it immediately.

    disconnect() releases only the link, never endpoint actors. Removing an
    endpoint disconnects its links before the body. Re-adding/cloning actors
    does not recreate links. No connection is added with stage.add().
    """

    __slots__ = ("_endpoints", "_native", "_world")
    _world: Physics
    _endpoints: tuple[Actor | Point, Actor | Point]
    _native: tuple[constraints.Constraint, ...]

    def __new__(cls) -> Self:
        raise TypeError("Create connections through stage.physics")

    @property
    def connected(self) -> bool:
        """Whether this handle still owns native constraints."""
        return bool(self._native)

    @property
    def a(self) -> Actor | Point:
        """First actor or fixed world-coordinate endpoint, readable after disconnect."""
        return self._endpoints[0]

    @property
    def b(self) -> Actor | Point:
        """Second actor or fixed world-coordinate endpoint, readable after disconnect."""
        return self._endpoints[1]

    @property
    def collide(self) -> bool:
        """Whether this link permits physical collision between its two bodies."""
        from ._connections import _require

        return bool(_require(self)[0].collide_bodies)

    @collide.setter
    def collide(self, value: bool) -> None:
        from ._connections import _require

        if not isinstance(value, bool):
            raise TypeError("collide must be bool")
        for native in _require(self):
            native.collide_bodies = value
            native.activate_bodies()

    def disconnect(self) -> None:
        """Release this link; repeated calls are harmless and do not remove actors."""
        from ._connections import _disconnect

        _disconnect(self)


class Rope(Connection):
    """A maximum-distance tether. It can go slack and does not push ends apart."""

    __slots__ = ()

    @property
    def length(self) -> float:
        """Positive maximum anchor separation in world pixels."""
        from ._connections import _require

        return float(cast("constraints.SlideJoint", _require(self)[0]).max)

    @length.setter
    def length(self, value: float) -> None:
        from ._connections import _require

        length = _positive(value, "length")
        native = cast("constraints.SlideJoint", _require(self)[0])
        native.max = length
        native.activate_bodies()


class Hinge(Connection):
    """Connected pivots with optional angular limits relative to their initial angle."""

    __slots__ = ()

    def motor(self, *, speed: float, max_torque: float) -> Motor:
        """Drive this hinge in clockwise degrees/second with finite positive torque.

        Only one connected motor is allowed. speed=0 brakes relative rotation;
        motor.disconnect() releases the drive while leaving the hinge free.
        """
        from ._connections import _motor

        return _motor(self, speed=speed, max_torque=max_torque)


class Spring(Connection):
    """A damped physical spring; native constraints own its current configuration."""

    __slots__ = ()

    @property
    def rest_length(self) -> float:
        """Positive resting anchor separation in world pixels."""
        return float(_spring(self).rest_length)

    @rest_length.setter
    def rest_length(self, value: float) -> None:
        amount = _positive(value, "rest_length")
        _spring(self).rest_length = amount
        _spring(self).activate_bodies()

    @property
    def stiffness(self) -> float:
        """Positive spring constant in game mass/second squared."""
        return float(_spring(self).stiffness)

    @stiffness.setter
    def stiffness(self, value: float) -> None:
        amount = _positive(value, "stiffness")
        _spring(self).stiffness = amount
        _spring(self).activate_bodies()

    @property
    def damping(self) -> float:
        """Nonnegative damping in game mass/second; larger values settle motion."""
        return float(_spring(self).damping)

    @damping.setter
    def damping(self, value: float) -> None:
        amount = _number(value, "damping", minimum=0)
        _spring(self).damping = amount
        _spring(self).activate_bodies()


class Motor(Connection):
    """One hinge's torque-limited drive; disconnecting the hinge also retires this motor."""

    __slots__ = ("_hinge",)
    _hinge: Hinge

    @property
    def speed(self) -> float:
        """Relative clockwise angular speed in degrees/second; zero actively brakes."""
        return degrees(float(_motor(self).rate))

    @speed.setter
    def speed(self, value: float) -> None:
        amount = radians(_number(value, "speed"))
        _motor(self).rate = amount
        _motor(self).activate_bodies()

    @property
    def max_torque(self) -> float:
        """Finite positive drive limit in game mass*pixels squared/seconds squared."""
        return float(_motor(self).max_force)

    @max_torque.setter
    def max_torque(self, value: float) -> None:
        amount = _positive(value, "max_torque")
        _motor(self).max_force = amount
        _motor(self).activate_bodies()

    @property
    def collide(self) -> bool:
        """Pair collision follows the connected hinge's single policy."""
        _motor(self)
        return self._hinge.collide

    @collide.setter
    def collide(self, value: bool) -> None:
        _motor(self)
        self._hinge.collide = value


def _spring(link: Spring) -> constraints.DampedSpring:
    from ._connections import _require

    return cast("constraints.DampedSpring", _require(link)[0])


def _motor(link: Motor) -> constraints.SimpleMotor:
    from ._connections import _require

    return cast("constraints.SimpleMotor", _require(link)[0])
