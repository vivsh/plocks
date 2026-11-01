"""Single-cell authored motion, reusing the bounded fiber tree and local clearance."""

from __future__ import annotations

from math import atan2, degrees, hypot
from typing import TYPE_CHECKING

from .errors import PhysicsError, StageError
from .geometry import Bounds, Point, _number
from .physics import Body, BodyType, _native

if TYPE_CHECKING:
    from ._commands import Actor, _MoveCell
    from ._operations import _CellMove
    from .tiling import TileMap


def _clear(actor: Actor, world: TileMap, start: Point, end: Point) -> bool:
    """Keep the whole footprint inside the map and sweep current obstacles."""
    from ._navigation import _clear as clear_tiles

    bounds = actor.bounds
    if isinstance(actor._transform, Body):
        bb = next(iter(_native(actor.body).shapes)).cache_bb()
        bounds = Bounds(bb.left, bb.bottom, bb.right, bb.top)
    footprint = Bounds(
        bounds.left - actor.x, bounds.bottom - actor.y, bounds.right - actor.x, bounds.top - actor.y
    )
    area = world.bounds
    if any(
        (
            p[0] + footprint.left < area.left - 1e-8
            or p[0] + footprint.right > area.right + 1e-8
            or p[1] + footprint.bottom < area.bottom - 1e-8
            or p[1] + footprint.top > area.top + 1e-8
        )
        for p in (start, end)
    ):
        return False
    if not isinstance(actor._transform, Body):
        return clear_tiles(world, start, end, footprint)
    length = hypot(end[0] - start[0], end[1] - start[1])
    angle = degrees(atan2(end[0] - start[0], end[1] - start[1]))
    return actor.body.can_travel(distance=length, direction=angle)


async def _move_cell(actor: Actor, command: _MoveCell) -> None:
    """Admit exactly one centered cardinal step without interrupting an existing step."""
    from ._operations import _CellMove, _context, _suspend
    from ._scripts import _actions, _conflicts, _fibers, _outer

    stage, root, _, at = await _context()
    world = command.world
    if actor._stage is not stage or world._stage is not stage:
        raise StageError("Actor and tile map must belong to the executing stage")
    for action in _actions(stage):
        for fiber in _fibers(action):
            if isinstance(fiber.waiting, _CellMove) and fiber.waiting.actor is actor:
                if _outer(action) is _outer(root):
                    raise StageError("During branches cannot control the same cell movement")
                return
    if isinstance(actor._transform, Body) and actor.body_type is not BodyType.KINEMATIC:
        raise PhysicsError("Cell movement requires a kinematic or nonphysical actor")
    cell = world.cell_at(x=actor.x, y=actor.y)
    if cell is None:
        raise ValueError("Start cell movement inside the map at a cell center")
    origin = world.cell_center(row=cell[0], column=cell[1])
    if hypot(actor.x - origin[0], actor.y - origin[1]) > 1e-6:
        raise ValueError("Start cell movement at a cell center (tolerance 0.000001 pixels)")
    dr, dc = {0: (-1, 0), 90: (0, 1), 180: (1, 0), 270: (0, -1)}[int(command.direction)]
    row, col = cell[0] + dr, cell[1] + dc
    if not (0 <= row < world.rows and 0 <= col < world.columns):
        return
    destination = world.cell_center(row=row, column=col)
    if not _clear(actor, world, origin, destination):
        return
    _number(at + command.seconds, "cell deadline")
    _conflicts(actor, True, True, root)
    if isinstance(actor._transform, Body):
        _native(actor.body).velocity = (0, 0)
    await _suspend(_CellMove(actor, world, origin, destination, at, command.seconds))


def _sample(request: _CellMove, now: float) -> bool:
    """Apply only a clear next increment; False asks the owner to cancel the root."""
    from .motion import _set_position

    if request.world._stage is not request.actor._stage:
        return False
    progress = min(1.0, max(0.0, (now - request.started) / request.seconds))
    if now + 1e-12 >= request.started + request.seconds:
        progress = 1.0
    x, y = request.origin
    ex, ey = request.destination
    destination = (
        _number((1 - progress) * x + progress * ex, "cell x"),
        _number((1 - progress) * y + progress * ey, "cell y"),
    )
    if not _clear(request.actor, request.world, request.actor.position, destination):
        return False
    _set_position(request.actor, destination)
    return True
