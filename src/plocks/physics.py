"""Optional rigid bodies in logical pixels, seconds, and game mass units."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import degrees, inf, radians
from typing import TYPE_CHECKING, Self

from .actions import Action
from .errors import PhysicsError
from .geometry import Point, _number, _point, _positive

if TYPE_CHECKING:
    import pymunk

    from ._commands import Actor
    from ._physics import _TileBody
    from .connections import Connection, Hinge, Rope, Spring
    from .puppets import Puppet
    from .sprites import Sprite
    from .stage import Stage
    from .tiling import TileMap


class BodyType(Enum):
    """Dynamic bodies respond to forces; kinematic bodies move platforms; static bodies stay put."""

    DYNAMIC = "dynamic"
    STATIC = "static"
    KINEMATIC = "kinematic"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class Box:
    """Fixed actor-local collision box, in unscaled pixels, centered at center."""

    width: float
    height: float
    center: Point = (0, 0)

    def __post_init__(self) -> None:
        _positive(self.width, "width")
        _positive(self.height, "height")
        object.__setattr__(self, "center", _point(self.center, "center"))


@dataclass(frozen=True, slots=True)
class Circle:
    """Fixed actor-local collision circle; costume transparency is irrelevant."""

    radius: float
    center: Point = (0, 0)

    def __post_init__(self) -> None:
        _positive(self.radius, "radius")
        object.__setattr__(self, "center", _point(self.center, "center"))


class Physics:
    """The native world belonging to one enabled Stage. Access through stage.physics.

    One-way/connected worlds adapt native precision to motion and collider size, without
    changing simulation time. PhysicsError stops execution if safe stepping would
    require more than 1024 native substeps per tick. Reduce speed/force, enlarge
    very small colliders, or increase the stage's tick_rate for that workload.
    """

    __slots__ = ("_bodies", "_connections", "_space", "_stage", "_terrain")

    def __init__(self, stage: Stage) -> None:
        try:
            import pymunk
        except ImportError as error:
            raise PhysicsError(
                "Pymunk is missing: reinstall plocks with its dependencies"
            ) from error
        self._stage = stage
        self._space: pymunk.Space | None = pymunk.Space(threaded=False)
        self._bodies: list[Body] = []
        self._connections: list[Connection] = []
        self._terrain: list[_TileBody] = []
        self._space.gravity = (0, -900)
        from ._physics import _ONE_WAY, _begin_one_way

        self._space.add_collision_handler(_ONE_WAY, 0).begin = _begin_one_way

    def rope(
        self,
        a: Actor | Point,
        b: Actor | Point,
        *,
        length: float | None = None,
        anchor_a: Point = (0, 0),
        anchor_b: Point = (0, 0),
        collide: bool = False,
    ) -> Rope:
        """Attach a maximum-distance rope; endpoints are actors or fixed world points.

        Actor anchors are unscaled local pixels. Omitted length captures current
        separation. At least one actor must be dynamic in this world. The returned
        rope is already connected; disconnect() releases it. Do not stage.add it.
        """
        from ._connections import _rope

        return _rope(
            self, a, b, length=length, anchor_a=anchor_a, anchor_b=anchor_b, collide=collide
        )

    def hinge(
        self,
        a: Actor | Point,
        b: Actor | Point,
        *,
        anchor_a: Point = (0, 0),
        anchor_b: Point = (0, 0),
        limits: tuple[float, float] | None = None,
        collide: bool = False,
    ) -> Hinge:
        """Connect local pivots; optional clockwise degree limits are relative to now.

        Limits include zero. Actor anchors are unscaled local pixels; Points are
        fixed world anchors. Attach actors first, aligning pivots before stepping.
        Removing an endpoint releases its connections. Call hinge.motor to drive.
        """
        from ._connections import _hinge

        return _hinge(
            self, a, b, anchor_a=anchor_a, anchor_b=anchor_b, limits=limits, collide=collide
        )

    def spring(
        self,
        a: Actor | Point,
        b: Actor | Point,
        *,
        rest_length: float | None = None,
        stiffness: float = 100,
        damping: float = 10,
        anchor_a: Point = (0, 0),
        anchor_b: Point = (0, 0),
        collide: bool = False,
    ) -> Spring:
        """Attach a damped spring; omitted rest_length captures current separation.

        Length is world pixels, stiffness positive mass/second squared, damping
        nonnegative mass/second. Large stiffness may exceed bounded stepping and
        raise PhysicsError. Use disconnect() to release; do not stage.add it.
        """
        from ._connections import _spring

        return _spring(
            self,
            a,
            b,
            rest_length=rest_length,
            stiffness=stiffness,
            damping=damping,
            anchor_a=anchor_a,
            anchor_b=anchor_b,
            collide=collide,
        )

    @property
    def gravity(self) -> Point:
        """World acceleration in pixels/second squared; default (0, -900)."""
        from ._physics import _space

        value = _space(self).gravity
        return float(value.x), float(value.y)

    @gravity.setter
    def gravity(self, value: Point) -> None:
        from ._physics import _space

        _space(self).gravity = _point(value, "gravity")


class Body:
    """One physical attachment, obtained through actor.body. Removal invalidates it.

    Re-adding the actor creates a new body with default velocity, shape and material.
    Dynamic movement uses velocity, impulses and forces. Kinematic movement may glide.
    """

    __slots__ = ("_actor", "_native", "_shape", "_world")
    _actor: Sprite | Puppet
    _world: Physics
    _native: pymunk.Body | None
    _shape: Box | Circle

    def __new__(cls) -> Self:
        """Bodies are created by stage membership; use actor.body."""
        raise TypeError("Bodies are created by a physics-enabled stage; use actor.body")

    @property
    def body_type(self) -> BodyType:
        """Attachment role; change actor.body_type only while detached."""
        native = _native(self)
        return {0: BodyType.DYNAMIC, 1: BodyType.KINEMATIC, 2: BodyType.STATIC}[native.body_type]

    @property
    def velocity(self) -> Point:
        """World pixels per second. Static bodies reject velocity assignment."""
        v = _native(self).velocity
        return float(v.x), float(v.y)

    @velocity.setter
    def velocity(self, value: Point) -> None:
        value = _point(value, "velocity")
        native = _native(self)
        if self.body_type is BodyType.STATIC:
            raise PhysicsError("Static bodies cannot have velocity")
        from ._scripts import _conflicts

        _conflicts(self._actor, True, True)
        native.velocity = value
        native.activate()

    @property
    def angular_velocity(self) -> float:
        """Clockwise degrees per second; independent of visual rotation_style."""
        return -degrees(_native(self).angular_velocity)

    @angular_velocity.setter
    def angular_velocity(self, value: float) -> None:
        value = _number(value, "angular_velocity")
        native = _native(self)
        if self.body_type is BodyType.STATIC or self.rotation_locked:
            raise PhysicsError("Angular velocity requires an unlocked moving body")
        from ._physics import _one_way

        if value and _one_way(self._actor):
            raise PhysicsError("One-way platforms must stay horizontal")
        native.angular_velocity = -radians(value)
        native.activate()

    @property
    def mass(self) -> float:
        """Positive game mass units on a dynamic body; default 1."""
        return float(_native(self).mass)

    @mass.setter
    def mass(self, value: float) -> None:
        value = _positive(value, "mass")
        native = _dynamic(self)
        from ._physics import _moment

        moment = inf if self.rotation_locked else _moment(self._shape, self._actor.scale, value)
        native.mass = value
        native.moment = moment
        native.activate()

    @property
    def sensor(self) -> bool:
        """Detect overlap without blocking. Gravity still applies; default False.

        Sensors cannot support grounded actors. Configure a static/kinematic role
        for stationary pickups. Removing/re-adding creates a default body.
        """
        return bool(next(iter(_native(self).shapes)).sensor)

    @sensor.setter
    def sensor(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("sensor must be bool")
        from ._physics import _one_way

        native = _native(self)
        if value and _one_way(self._actor):
            raise PhysicsError("A one-way platform cannot be a sensor")
        for shape in native.shapes:
            shape.sensor = value
        native.activate()

    @property
    def friction(self) -> float:
        """Finite nonnegative contact friction; default 0.7."""
        return float(next(iter(_native(self).shapes)).friction)

    @friction.setter
    def friction(self, value: float) -> None:
        value = _number(value, "friction", minimum=0)
        for shape in _native(self).shapes:
            shape.friction = value

    @property
    def bounce(self) -> float:
        """Contact elasticity from 0 (inelastic) to 1; default 0."""
        return float(next(iter(_native(self).shapes)).elasticity)

    @bounce.setter
    def bounce(self, value: float) -> None:
        value = _number(value, "bounce", minimum=0)
        if value > 1:
            raise ValueError("bounce must be at most 1")
        for shape in _native(self).shapes:
            shape.elasticity = value

    @property
    def rotation_locked(self) -> bool:
        """Whether dynamic rotation is constrained using infinite native inertia."""
        return _native(self).moment == inf and self.body_type is BodyType.DYNAMIC

    @rotation_locked.setter
    def rotation_locked(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("rotation_locked must be bool")
        native = _dynamic(self)
        from ._connections import _check_rotation
        from ._physics import _moment

        _check_rotation(self, value)
        native.moment = inf if value else _moment(self._shape, self._actor.scale, native.mass)
        if value:
            native.angular_velocity = 0
        native.activate()

    @property
    def shape(self) -> Box | Circle:
        """Unscaled collider definition; appearance changes do not resize it.

        One-way platforms require Box and collide along its top edge only.
        """
        _native(self)
        return self._shape

    @shape.setter
    def shape(self, value: Box | Circle) -> None:
        if not isinstance(value, (Box, Circle)):
            raise TypeError("Use a Box or Circle")
        from ._physics import _replace_shape

        _replace_shape(self, value, self._actor.scale)

    @property
    def grounded(self) -> bool:
        """Current supporting contact against gravity, excluding separating/stale contacts."""
        from ._physics import _grounded

        return _grounded(self)

    def touching(self, other: Body | TileMap) -> bool:
        """Test current physical contacts; actor.touching remains visual AABB overlap."""
        from ._physics import _touching

        return _touching(self, other)

    def impulse(
        self, *, x: float = 0, y: float = 0, at: Point | None = None, after: Action | None = None
    ) -> Action:
        """Schedule a one-time world impulse in mass*pixels/second; at is a world point."""
        from ._commands import _Impulse, _schedule

        _dynamic(self)
        return _schedule(self._actor, _Impulse(self, x, y, at), after=after)

    def force(
        self,
        *,
        x: float = 0,
        y: float = 0,
        seconds: float | None = None,
        at: Point | None = None,
        after: Action | None = None,
    ) -> Action:
        """Apply world force over simulated seconds; omit seconds for one fixed step."""
        from ._commands import _Force, _schedule

        _dynamic(self)
        return _schedule(self._actor, _Force(self, x, y, seconds, at), after=after)

    def torque(
        self, amount: float, *, seconds: float | None = None, after: Action | None = None
    ) -> Action:
        """Apply clockwise torque in mass*pixels²/second², for one step or a duration."""
        from ._commands import _schedule, _Torque

        _dynamic(self)
        return _schedule(self._actor, _Torque(self, amount, seconds), after=after)


def _native(body: Body) -> pymunk.Body:
    if body._native is None or body._world._space is None:
        raise PhysicsError("This body was removed; use the actor's current body after re-adding")
    return body._native


def _dynamic(body: Body) -> pymunk.Body:
    native = _native(body)
    if body.body_type is not BodyType.DYNAMIC:
        raise PhysicsError("Impulses, forces and mass require a dynamic body")
    return native
