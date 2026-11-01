"""Point-side queries report inclusive half-spaces without changing rectangle state."""

from dataclasses import fields
from typing import cast

import pytest

from plocks import Bounds, Edge, Point


@pytest.mark.parametrize(
    "point, expected",
    [
        ((0, 0), frozenset()),
        ((-10, 0), frozenset({Edge.LEFT})),
        ((10, 0), frozenset({Edge.RIGHT})),
        ((0, -5), frozenset({Edge.BOTTOM})),
        ((0, 5), frozenset({Edge.TOP})),
        ((-10, -5), frozenset({Edge.LEFT, Edge.BOTTOM})),
        ((-10, 5), frozenset({Edge.LEFT, Edge.TOP})),
        ((10, -5), frozenset({Edge.RIGHT, Edge.BOTTOM})),
        ((10, 5), frozenset({Edge.RIGHT, Edge.TOP})),
        ((-100, 0), frozenset({Edge.LEFT})),
        ((100, 0), frozenset({Edge.RIGHT})),
        ((0, -100), frozenset({Edge.BOTTOM})),
        ((0, 100), frozenset({Edge.TOP})),
        ((-100, 100), frozenset({Edge.LEFT, Edge.TOP})),
        ((100, -100), frozenset({Edge.RIGHT, Edge.BOTTOM})),
        ((9.999, -4.999), frozenset()),
    ],
)
def test_point_sides_include_boundaries_and_outside_regions(
    point: Point, expected: frozenset[Edge]
) -> None:
    area = Bounds(-10, -5, 10, 5)
    assert area.edges_at(point) == expected


def test_contains_and_point_edges_answer_different_questions() -> None:
    area = Bounds(20, 30, 60, 70)
    assert area.contains((20, 50)) and area.edges_at((20, 50)) == frozenset({Edge.LEFT})
    assert area.contains((40, 50)) and not area.edges_at((40, 50))
    assert not area.contains((80, 90))
    assert area.edges_at((80, 90)) == frozenset({Edge.RIGHT, Edge.TOP})


@pytest.mark.parametrize(
    "area, point, expected",
    [
        (Bounds(0, 0, 0, 0), (0, 0), frozenset(Edge)),
        (Bounds(0, 0, 0, 0), (1, 0), frozenset({Edge.RIGHT, Edge.TOP, Edge.BOTTOM})),
        (Bounds(0, -5, 0, 5), (0, 0), frozenset({Edge.LEFT, Edge.RIGHT})),
        (Bounds(-10, 0, 10, 0), (0, 0), frozenset({Edge.TOP, Edge.BOTTOM})),
    ],
)
def test_degenerate_bounds_preserve_inclusive_sides(
    area: Bounds, point: Point, expected: frozenset[Edge]
) -> None:
    assert area.edges_at(point) == expected


@pytest.mark.parametrize("point", [(float("nan"), 0), (0, float("inf")), (float("-inf"), 0)])
def test_nonfinite_coordinates_are_rejected(point: Point) -> None:
    with pytest.raises(ValueError):
        Bounds(-10, -5, 10, 5).edges_at(point)


@pytest.mark.parametrize("coordinate", [True, "left", None])
def test_nonnumeric_coordinates_use_existing_point_validation(coordinate: object) -> None:
    with pytest.raises(TypeError):
        Bounds(-10, -5, 10, 5).edges_at((cast(float, coordinate), 0))


def test_results_are_independent_values_and_bounds_keep_their_four_fields() -> None:
    area = Bounds(-10, -5, 10, 5)
    result = area.edges_at((10, 5))
    assert area.edges_at((0, 0)) == frozenset()
    assert result == frozenset({Edge.RIGHT, Edge.TOP})
    assert area == Bounds(-10, -5, 10, 5)
    assert tuple(field.name for field in fields(Bounds)) == ("left", "bottom", "right", "top")
