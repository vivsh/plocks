"""Small combat helpers; all geometry and decisions are operation-local."""

from __future__ import annotations

from math import sqrt
from typing import TYPE_CHECKING

from .errors import PhysicsError, StageError
from .geometry import _number, _positive
from .physics import _native
from .queries import CastIgnore, CastTarget

if TYPE_CHECKING:
    import pymunk

    from ._commands import Actor
    from .actions import Action
    from .physics import Body, Physics


def _walk(body: Body, speed: float, current: Action | None = None) -> None:
    """Set horizontal velocity without claiming the vertical motion channel."""
    from ._scripts import _conflicts
    from .physics import BodyType, _native

    speed = _number(speed, "speed")
    native = _native(body)
    if body.body_type is BodyType.STATIC:
        raise PhysicsError("Static bodies cannot walk")
    _conflicts(body._actor, True, False, current)
    native.velocity = (speed, native.velocity.y)
    native.activate()


def _jump(body: Body, height: float, current: Action | None = None) -> bool:
    """Launch a grounded dynamic body against strictly downward vertical gravity."""
    from ._scripts import _conflicts
    from .physics import _dynamic

    height = _positive(height, "height")
    native = _dynamic(body)
    gx, gy = body._world.gravity
    if gx != 0 or gy >= 0:
        raise PhysicsError("jump requires downward vertical gravity (0, negative)")
    speed = _number(sqrt(2 * -gy * height), "jump speed")
    if not body.grounded:
        return False
    _conflicts(body._actor, False, True, current)
    native.velocity = (native.velocity.x, speed)
    native.activate()
    return True


def _can_see(actor: Actor, other: Actor, distance: float | None, ignore: CastIgnore) -> bool:
    """Check range and opaque physics geometry between two attached actor anchors."""
    from ._casts import _filter
    from .puppets import Puppet
    from .sprites import Sprite
    from .stage import _attached

    if not isinstance(other, (Sprite, Puppet)):
        raise TypeError("can_see requires a Sprite or Puppet")
    limit = None if distance is None else _number(distance, "distance", minimum=0)
    skipped = _filter(ignore)
    stage = _attached(actor)
    if other._stage is not stage:
        raise StageError("Sight targets must belong to the same stage")
    world = stage.physics
    separation = actor.distance_to(other)
    if limit is not None and separation > limit:
        return False
    if not separation:
        return True

    def exclude(target: CastTarget) -> bool:
        return target is actor or skipped(target)

    hit = world.raycast(actor.position, other.position, ignore=exclude)
    return hit is None or hit.target is other


def _group(value: str) -> str:
    """Validate a named collision category before changing a body."""
    if not isinstance(value, str):
        raise TypeError("Collision group names must be strings")
    if not value.strip():
        raise ValueError("Collision group names must not be empty")
    return value


def _wake(world: Physics) -> None:
    for body in world._bodies:
        _native(body).activate()


def _pair(world: Physics, first: pymunk.Body, second: pymunk.Body) -> bool:
    """Borrow named rules; terrain has no Python collision-configuration owner."""
    a = next((body for body in world._bodies if body._native is first), None)
    b = next((body for body in world._bodies if body._native is second), None)
    ag, bg = (
        ("terrain" if a is None else a._collision_group),
        ("terrain" if b is None else b._collision_group),
    )
    return (a is None or a._collides_with is None or bg in a._collides_with) and (
        b is None or b._collides_with is None or ag in b._collides_with
    )


def _install_filter(world: Physics) -> None:
    """Install one stateless pair test, preserving native one-way begin semantics."""
    from ._physics import _ONE_WAY, _space

    def accept(arbiter: pymunk.Arbiter, space: pymunk.Space, data: object) -> bool:
        a, b = arbiter.shapes
        return a.body is not None and b.body is not None and _pair(world, a.body, b.body)

    space = _space(world)
    space.add_default_collision_handler().pre_solve = accept
    space.add_collision_handler(_ONE_WAY, 0).pre_solve = accept
