"""Bounded grid searches; all search and clearance scratch belongs to one query."""

from __future__ import annotations

from heapq import heappop, heappush
from math import floor
from typing import TYPE_CHECKING

from .errors import NavigationError
from .geometry import Bounds, Point, _integer, _point

if TYPE_CHECKING:
    from ._commands import Actor
    from .tiling import TileMap

type _Cell = tuple[int, int]


def _intersects_segment(a: Point, b: Point, bounds: Bounds) -> bool:
    """Intersect the open obstacle interior so edge-only contact remains allowed."""
    enter, leave = 0.0, 1.0
    for start, end, low, high in (
        (a[0], b[0], bounds.left, bounds.right),
        (a[1], b[1], bounds.bottom, bounds.top),
    ):
        delta = end - start
        if delta == 0:
            if not low < start < high:
                return False
        else:
            first, last = (low - start) / delta, (high - start) / delta
            enter, leave = max(enter, min(first, last)), min(leave, max(first, last))
            if enter >= leave:
                return False
    return enter < leave


def _clear(grid: TileMap, a: Point, b: Point, footprint: Bounds) -> bool:
    """Sweep a fixed rectangle against nearby tiles without a spatial index."""
    swept = Bounds(
        min(a[0], b[0]) + footprint.left,
        min(a[1], b[1]) + footprint.bottom,
        max(a[0], b[0]) + footprint.right,
        max(a[1], b[1]) + footprint.top,
    )
    area = grid.bounds
    if (
        swept.left < area.left
        or swept.right > area.right
        or swept.bottom < area.bottom
        or swept.top > area.top
    ):
        return False
    w, h = grid.tile_size
    left = max(0, floor((swept.left - grid.x) / w))
    right = min(grid.columns, floor((swept.right - grid.x) / w) + 1)
    top = max(0, floor((grid.y - swept.top) / h))
    bottom = min(grid.rows, floor((grid.y - swept.bottom) / h) + 1)
    for row in range(top, bottom):
        for col in range(left, right):
            key = grid._cells[row][col]
            if key is not None and (key in grid.solid or key in grid.one_way):
                x, y = grid.x + col * w, grid.y - row * h
                expanded = Bounds(
                    x - footprint.right,
                    y - h - footprint.top,
                    x + w - footprint.left,
                    y - footprint.bottom,
                )
                if _intersects_segment(a, b, expanded):
                    return False
    return True


def _route(
    grid: TileMap, previous: dict[_Cell, _Cell | None], last: _Cell, start: Point, goal: Point
) -> tuple[Point, ...]:
    cells: list[_Cell] = []
    cell: _Cell | None = last
    while cell is not None:
        cells.append(cell)
        cell = previous[cell]
    points = [start]
    for row, column in reversed(cells):
        point = grid.cell_center(row=row, column=column)
        if point != points[-1]:
            points.append(point)
    if points[-1] != goal:
        points.append(goal)
    return tuple(points)


def _find(
    grid: TileMap, start: Point, goal: Point, actor: Actor | None, max_nodes: int
) -> tuple[Point, ...] | None:
    """Search four-neighbor cells with unit costs and deterministic Manhattan A*."""
    from .puppets import Puppet
    from .sprites import Sprite

    start, goal = _point(start, "start"), _point(goal, "goal")
    limit = _integer(max_nodes, "max_nodes", minimum=1)
    first, last = grid.cell_at(x=start[0], y=start[1]), grid.cell_at(x=goal[0], y=goal[1])
    if first is None or last is None:
        raise ValueError("Path start and goal must be inside the tile map")
    footprint = Bounds(0, 0, 0, 0)
    if actor is not None:
        if not isinstance(actor, (Sprite, Puppet)):
            raise TypeError("actor must be a Sprite, Puppet or None")
        b = actor.bounds
        footprint = Bounds(b.left - actor.x, b.bottom - actor.y, b.right - actor.x, b.top - actor.y)
    for row, column in (first, last):
        key = grid._cells[row][column]
        if key is not None and (key in grid.solid or key in grid.one_way):
            return None
    if not _clear(grid, start, start, footprint) or not _clear(grid, goal, goal, footprint):
        return None
    if first == last:
        return (
            ((start,) if start == goal else (start, goal))
            if _clear(grid, start, goal, footprint)
            else None
        )
    first_center = grid.cell_center(row=first[0], column=first[1])
    last_center = grid.cell_center(row=last[0], column=last[1])
    if not _clear(grid, start, first_center, footprint) or not _clear(
        grid, last_center, goal, footprint
    ):
        return None
    costs = {first: 0}
    previous: dict[_Cell, _Cell | None] = {first: None}
    frontier = [(abs(first[0] - last[0]) + abs(first[1] - last[1]), 0, *first)]
    expanded = 0
    while frontier:
        _, cost, row, col = heappop(frontier)
        cell = (row, col)
        if costs.get(cell) != cost:
            continue
        if cell == last:
            return _route(grid, previous, last, start, goal)
        if expanded >= limit:
            raise NavigationError(
                f"Path search exceeded max_nodes={limit}; increase the budget or use a smaller map"
            )
        expanded += 1
        origin = grid.cell_center(row=row, column=col)
        for nr, nc in ((row - 1, col), (row, col - 1), (row, col + 1), (row + 1, col)):
            if not (0 <= nr < grid.rows and 0 <= nc < grid.columns):
                continue
            neighbor = (nr, nc)
            if cost + 1 >= costs.get(neighbor, float("inf")):
                continue
            point = grid.cell_center(row=nr, column=nc)
            if not _clear(grid, origin, point, footprint):
                continue
            costs[neighbor], previous[neighbor] = cost + 1, cell
            heappush(frontier, (cost + 1 + abs(nr - last[0]) + abs(nc - last[1]), cost + 1, nr, nc))
    return None
