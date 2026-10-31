"""Operation-local configuration-space geometry for continuous translational sweeps."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .geometry import Point, _number, _point

if TYPE_CHECKING:
    import pymunk


def _hull(points: list[Point]) -> list[Point]:
    """Convex hull of a finite point set; scratch is local to one expansion."""
    unique = sorted(set(points))
    if len(unique) < 3:
        return unique

    def cross(a: Point, b: Point, c: Point) -> float:
        return _number(
            (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]), "sweep geometry"
        )

    def half(values: list[Point]) -> list[Point]:
        result: list[Point] = []
        for value in values:
            while len(result) >= 2 and cross(result[-2], result[-1], value) <= 0:
                result.pop()
            result.append(value)
        return result

    return half(unique)[:-1] + half(list(reversed(unique)))[:-1]


def _core(shape: pymunk.Shape) -> tuple[list[Point], float]:
    """Borrow native convex core vertices in world space and its rounding radius."""
    import pymunk

    body = shape.body
    assert body is not None
    if isinstance(shape, pymunk.Circle):
        vertices = [shape.offset]
    elif isinstance(shape, pymunk.Segment):
        vertices = [shape.a, shape.b]
    elif isinstance(shape, pymunk.Poly):
        vertices = shape.get_vertices()
    else:
        raise TypeError("Unsupported native collision geometry")
    return [_point(tuple(body.local_to_world(v))) for v in vertices], float(shape.radius)


def _expanded(shape: pymunk.Shape, offsets: tuple[Point, ...], radius: float) -> pymunk.Shape:
    """Build the obstacle minus the moving core, without adding it to a Space."""
    import pymunk

    core, rounding = _core(shape)
    hull = _hull([_point((x - dx, y - dy)) for x, y in core for dx, dy in offsets])
    body = pymunk.Body(body_type=pymunk.Body.STATIC)
    total_radius = _number(radius + rounding, "sweep radius")
    if len(hull) == 1:
        result: pymunk.Shape = pymunk.Circle(body, total_radius, hull[0])
    elif len(hull) == 2:
        result = pymunk.Segment(body, hull[0], hull[1], total_radius)
    else:
        result = pymunk.Poly(body, hull, radius=total_radius)
    result.cache_bb()
    return result


def _witness(
    shape: pymunk.Shape, anchor: Point, offsets: tuple[Point, ...], normal: Point
) -> Point:
    """Intersect source and target support features to recover a real contact point.

    Nearest-point projection from a source face's midpoint can land on another
    target face when a long box touches a rotated corner. Both support intervals
    lie on the contact plane, so their tangent overlap gives the actual witness.
    """
    nx, ny = normal
    tx, ty = -ny, nx
    core, rounding = _core(shape)
    source_plane = min(x * nx + y * ny for x, y in offsets)
    target_plane = max(x * nx + y * ny for x, y in core)
    source = [
        (anchor[0] + x) * tx + (anchor[1] + y) * ty
        for x, y in offsets
        if abs(x * nx + y * ny - source_plane) <= 1e-8
    ]
    target = [x * tx + y * ty for x, y in core if abs(x * nx + y * ny - target_plane) <= 1e-8]
    low, high = max(min(source), min(target)), min(max(source), max(target))
    tangent = (low + high) / 2
    if low > high + 1e-8:
        # A deep initial overlap has no unique contact; choose a point on the
        # target support feature closest to the source feature's midpoint.
        tangent = max(min(target), min(max(target), (min(source) + max(source)) / 2))
    plane = target_plane + rounding
    return _point((nx * plane + tx * tangent, ny * plane + ty * tangent))


def _sweep(
    shape: pymunk.Shape,
    start: Point,
    end: Point,
    offsets: tuple[Point, ...],
    radius: float,
    *,
    movement: bool,
    slop: float,
) -> tuple[float, Point, Point] | None:
    """Return travel fraction, target point and outward normal for one convex target.

    Minkowski expansion plus a native segment query sweeps the entire interval,
    including thin obstacles and rounded corners; no stepping approximation.
    """
    expanded = _expanded(shape, offsets, radius)
    dx, dy = end[0] - start[0], end[1] - start[1]
    try:
        initial = expanded.point_query(start)
        normal = float(initial.gradient.x), float(initial.gradient.y)
        approach = dx * normal[0] + dy * normal[1]
        if initial.distance <= 1e-8:
            if movement and approach >= -1e-8 and initial.distance >= -slop - 1e-8:
                return None
            if not movement:
                return 0.0, start, (0.0, 0.0)
            return 0.0, _witness(shape, start, offsets, normal), normal
        if dx == 0 and dy == 0:
            return None
        hit = expanded.segment_query(start, end, 0)
        if hit.shape is None:
            return None
        normal = float(hit.normal.x), float(hit.normal.y)
        if movement and dx * normal[0] + dy * normal[1] >= -1e-8:
            return None
        anchor = start[0] + dx * hit.alpha, start[1] + dy * hit.alpha
        return float(hit.alpha), _witness(shape, anchor, offsets, normal), normal
    finally:
        expanded.body = None
