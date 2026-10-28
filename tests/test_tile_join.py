"""Joining finite tile sections without sharing mutable cell state."""

import pytest
from PIL import Image as PillowImage

from plocks import Image, Stage, TileMap
from plocks._runtime import close


def test_horizontal_join_and_editable_physics_world() -> None:
    """Identical but independently created palette images join; cells and terrain are independent."""
    left = TileMap(
        ["#.", "##"],
        {"#": Image.rectangle(8, 8, color="red")},
        tile_size=(8, 8),
        solid={"#"},
        x=-16,
        y=8,
        layer=3,
    )
    right = TileMap(
        [".#", "##"],
        {"#": Image.rectangle(8, 8, color="red")},
        tile_size=(8, 8),
        solid={"#"},
        x=400,
        y=300,
        layer=9,
    )
    result = left.join(right, direction="right")
    assert result.cells == (("#", None, None, "#"), ("#", "#", "#", "#"))
    assert result.position == left.position and result.layer == 3
    assert (result.rows, result.columns, result.bounds.right) == (2, 4, 16)
    stage = Stage(physics=True)
    try:
        stage.add(result)
        result.set_tile(row=0, column=3, tile=None)
        assert right.get_tile(row=0, column=1) == "#"
        left.set_tile(row=1, column=0, tile=None)
        assert result.get_tile(row=1, column=0) == "#"
        assert result.solid == frozenset({"#"})
    finally:
        close(stage)


def test_vertical_join_combines_distinct_palettes_and_preserves_style() -> None:
    """Down appends rows; distinct solid and one-way keys keep their collision meaning."""
    top = TileMap(
        [["leaf", None]],
        {"leaf": Image.rectangle(4, 4, color="green")},
        tile_size=(4, 4),
        x=9,
        y=30,
        visible=False,
        layer=4,
        opacity=0.7,
        parallax_origin=(2, 3),
    )
    bottom = TileMap(
        [["wall", "ledge"]],
        {"wall": Image.rectangle(4, 4, color="red"), "ledge": Image.rectangle(4, 4, color="blue")},
        tile_size=(4, 4),
        solid={"wall"},
        one_way={"ledge"},
    )
    result = top.join(bottom, direction="down")
    assert result.cells == (("leaf", None), ("wall", "ledge"))
    assert result.position == (9, 30) and result.visible is False and result.layer == 4
    assert result.opacity == 0.7 and result.parallax_origin == (2, 3)
    assert result.solid == frozenset({"wall"}) and result.one_way == frozenset({"ledge"})
    assert result.cell_center(row=1, column=1) == (15, 24)
    assert result.palette["wall"] is bottom.palette["wall"]


def test_join_reuse_and_anchors_do_not_affect_tiles() -> None:
    """Sections can be reused in chains; image anchors do not alter tile placement."""
    source = Image(PillowImage.new("RGBA", (3, 3), "red"))
    a = TileMap(["#"], {"#": source}, tile_size=(3, 3))
    b = TileMap(["#"], {"#": source.with_anchor(0, 0)}, tile_size=(3, 3))
    result = a.join(b, direction="right").join(a, direction="right")
    assert result.cells == (("#", "#", "#"),)
    assert result.palette["#"] is source
    a.set_tile(row=0, column=0, tile=None)
    assert result.cells == (("#", "#", "#"),)


@pytest.mark.parametrize("direction", ["right", "down"])
def test_incompatible_dimensions_do_not_mutate_sources(direction: str) -> None:
    """A mismatched shared axis fails before either map changes."""
    from typing import Literal, cast

    tile = Image.rectangle(4, 4, color="red")
    a = TileMap(["##"], {"#": tile}, tile_size=(4, 4))
    b = TileMap(["#", "#"], {"#": tile}, tile_size=(4, 4))
    before = (a.cells, b.cells)
    with pytest.raises(ValueError, match="same number"):
        a.join(b, direction=cast(Literal["right", "down"], direction))
    assert (a.cells, b.cells) == before


def test_join_rejects_conflicting_images_collisions_and_tilesizes() -> None:
    """Conflicting shared keys and incompatible tile sizes fail with useful errors."""
    red = Image.rectangle(4, 4, color="red")
    blue = Image.rectangle(4, 4, color="blue")
    a = TileMap(["#"], {"#": red}, tile_size=(4, 4), solid={"#"})
    with pytest.raises(ValueError, match="Conflicting images"):
        a.join(TileMap(["#"], {"#": blue}, tile_size=(4, 4), solid={"#"}), direction="right")
    with pytest.raises(ValueError, match="Conflicting collision"):
        a.join(TileMap(["#"], {"#": red}, tile_size=(4, 4)), direction="right")
    with pytest.raises(ValueError, match="Conflicting collision"):
        a.join(TileMap(["#"], {"#": red}, tile_size=(4, 4), one_way={"#"}), direction="down")
    with pytest.raises(ValueError, match="tile size"):
        a.join(TileMap(["#"], {"#": red}, tile_size=(8, 4), solid={"#"}), direction="right")
    assert a.cells == (("#",),) and a.solid == frozenset({"#"})


def test_join_rejects_physical_palette_with_parallax_from_first() -> None:
    """The existing solid-map parallax safety rule remains enforced on the resulting map."""
    a = TileMap(
        ["a"], {"a": Image.rectangle(2, 2, color="red")}, tile_size=(2, 2), parallax=(0.5, 1)
    )
    b = TileMap(["b"], {"b": Image.rectangle(2, 2, color="blue")}, tile_size=(2, 2), solid={"b"})
    with pytest.raises(ValueError, match="solid maps"):
        a.join(b, direction="right")


def test_extend_rows_down_and_right_reuses_map_configuration() -> None:
    """Row fragments produce independent maps with the existing palette, solids and style."""
    tile = Image.rectangle(4, 4, color="red")
    source = TileMap(["#.", "##"], {"#": tile}, tile_size=(4, 4), solid={"#"}, x=-9, y=20, layer=3)
    lower = source.extend([".#", "##"])
    right = source.extend(["..", "##"], direction="right")
    assert lower.cells == (("#", None), ("#", "#"), (None, "#"), ("#", "#"))
    assert right.cells == (("#", None, None, None), ("#", "#", "#", "#"))
    assert lower.palette["#"] is tile and right.palette["#"] is tile
    assert lower.solid == right.solid == source.solid
    assert lower.position == right.position == source.position and lower.layer == right.layer == 3
    lower.set_tile(row=0, column=0, tile=None)
    source.set_tile(row=1, column=1, tile=None)
    assert right.get_tile(row=1, column=1) == "#"
    assert lower.get_tile(row=1, column=1) == "#"


def test_extend_explicit_keys_and_custom_empty_marker() -> None:
    """Extension supports named-key matrix rows and the existing custom empty marker."""
    tile = Image.rectangle(4, 4, color="red")
    named = TileMap([["ground", None]], {"ground": tile}, tile_size=(4, 4), solid={"ground"})
    result = named.extend([[None, "ground"]])
    assert result.cells == (("ground", None), (None, "ground"))
    assert result.solid == frozenset({"ground"})
    mixed = TileMap([["ground", "a"]], {"ground": tile, "a": tile}, tile_size=(4, 4))
    assert mixed.extend(["a."]).cells == (("ground", "a"), ("a", None))
    short = TileMap(["##"], {"#": tile}, tile_size=(4, 4))
    assert short.extend([" #"], empty=" ").cells == (("#", "#"), (None, "#"))


def test_extend_rejects_bad_rows_without_mutating_source() -> None:
    """Empty, unknown, uneven and incompatible fragments fail before changing the map."""
    source = TileMap(["##", ".."], {"#": Image.rectangle(4, 4, color="red")}, tile_size=(4, 4))
    before = source.cells
    with pytest.raises(ValueError):
        source.extend([])
    with pytest.raises(KeyError):
        source.extend(["?$"])
    with pytest.raises(ValueError, match="same number of columns"):
        source.extend(["###"])
    with pytest.raises(ValueError, match="same number of rows"):
        source.extend(["#"], direction="right")
    with pytest.raises(ValueError):
        source.extend(["#", "##"], direction="right")
    assert source.cells == before
