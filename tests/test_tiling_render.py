from plocks.motion import _bounce, _move, _point_towards, _random

"""World/grid addressing, solid queries, clipping, and rendered camera behavior."""

import pygame
import pytest
from PIL import Image as PillowImage

from plocks import (
    Bounds,
    Image,
    Joint,
    Puppet,
    Skeleton,
    Sprite,
    Stage,
    TiledBackground,
    TileMap,
)
from plocks._render import frame
from plocks.geometry import _rotate


def tilemap() -> TileMap:
    """Two occupied cells, only one solid, with an explicit world top-left."""
    return TileMap(
        ["#.", ".x"],
        {
            "#": PillowImage.new("RGBA", (2, 2), "green"),
            "x": PillowImage.new("RGBA", (2, 2), "blue"),
        },
        tile_size=(10, 10),
        solid={"#"},
        x=-10,
        y=10,
    )


def test_cell_addressing_edges_and_editing() -> None:
    """Cell lookup and mutation follow top-left row/column semantics at exact edges."""
    world = tilemap()
    assert world.cell_at(x=-10, y=10) == (0, 0)
    assert world.cell_at(x=0, y=0) == (1, 1)
    assert world.cell_at(x=10, y=0) is None
    assert world.cell_at(x=0, y=-10) is None
    assert world.get_tile(row=0, column=1) is None
    before = world.cells
    world.set_tile(row=0, column=1, tile="#")
    assert before[0][1] is None
    assert world.get_tile(row=0, column=1) == "#"
    world.set_tile(row=0, column=1, tile=None)
    with pytest.raises(KeyError):
        world.set_tile(row=0, column=0, tile="z")
    with pytest.raises(IndexError):
        world.get_tile(row=-1, column=0)


def test_solid_overlap_not_empty_area_or_edges() -> None:
    """Queries report occupied cells, with optional solidity and no edge-only overlap."""
    world = tilemap()
    assert world.tiles_touching(Bounds(-20, -20, 20, 20)) == ((0, 0),)
    assert world.tiles_touching(Bounds(-20, -20, 20, 20), solid_only=False) == ((0, 0), (1, 1))
    assert world.tiles_touching(Bounds(0, 1, 2, 3)) == ()
    sprite = Sprite(PillowImage.new("RGBA", (2, 2)), x=-5, y=5, visible=False)
    assert sprite.touching(world)
    sprite.position = (5, -5)
    assert not sprite.touching(world)
    world.set_tile(row=0, column=0, tile=None)
    assert world.tiles_touching(world.bounds) == ()


def test_camera_layers_background_clip_and_overlay() -> None:
    """Scene members use the camera, repeating areas clip, and overlays use stage coordinates."""
    stage = Stage(20, 20, background="red")
    stage._target = pygame.display.set_mode((20, 20))
    stage.add(TiledBackground(PillowImage.new("RGBA", (1, 1), "green"), area=Bounds(-2, -2, 2, 2)))
    sprite = Sprite(PillowImage.new("RGBA", (2, 2), "blue"), x=5, y=0, layer=1)
    stage.add(sprite)
    stage.camera = (5, 0)
    frame(stage)
    assert stage._target.get_at((10, 10))[:3] == (0, 0, 255)
    assert stage._target.get_at((8, 8))[:3] == (0, 128, 0)
    assert stage._target.get_at((0, 0))[:3] == (255, 0, 0)
    assert stage._target.get_clip() == pygame.Rect(0, 0, 20, 20)
    sprite.visible = False
    frame(stage)
    assert stage._target.get_at((10, 10))[:3] == (0, 128, 0)


def test_background_large_area_is_bounded_by_viewport() -> None:
    """A huge repeating area must render only the visible cells, not traverse offscreen space."""
    stage = Stage(8, 8)
    stage._target = pygame.display.set_mode((8, 8))
    stage.add(
        TiledBackground(
            PillowImage.new("RGBA", (2, 2), "blue"),
            area=Bounds(-1_000_000, -1_000_000, 1_000_000, 1_000_000),
        )
    )
    frame(stage)
    assert stage._target.get_at((0, 0))[:3] == (0, 0, 255)


def test_figures_tiles_and_anchors_render_in_world() -> None:
    """The renderer handles articulated geometry and fits tiles without applying image anchors."""
    stage = Stage(40, 40)
    stage._target = pygame.display.set_mode((40, 40))
    image = Image(PillowImage.new("RGBA", (2, 2), "green"), anchor=(100, 100))
    stage.add(TileMap(["#"], {"#": image}, tile_size=(10, 10), x=-20, y=20))
    rig = Skeleton({"root": Joint(None), "hand": Joint("root", (0, 10))})
    stage.add(
        Puppet(
            rig,
            parts={
                "root": PillowImage.new("RGBA", (6, 6), "white"),
                "hand": PillowImage.new("RGBA", (3, 3), "white"),
            },
        )
    )
    frame(stage)
    assert stage._target.get_at((1, 1))[:3] == (0, 128, 0)
    assert stage._target.get_at((20, 20))[:3] == (255, 255, 255)
    assert stage._target.get_at((20, 10))[:3] == (255, 255, 255)


def test_transparency_and_edge_contact_are_explicit() -> None:
    """AABBs include transparent pixels, but touching at an edge is not overlap."""
    a = Sprite(PillowImage.new("RGBA", (10, 10)))
    b = Sprite(PillowImage.new("RGBA", (10, 10)), x=10)
    assert not a.touching(b)
    b.x = 9
    assert a.touching(b)


@pytest.mark.parametrize("direction", [0, 90, 180, 270])
def test_rotated_anchor_pixel_placement(direction: float) -> None:
    """An off-center anchor stays in place through cardinal rotations and scaling."""
    stage = Stage(40, 40)
    stage._target = pygame.display.set_mode((40, 40))
    image = PillowImage.new("RGBA", (4, 6), "red")
    sprite = Sprite(Image(image, anchor=(0, 0)), direction=direction, scale=2)
    stage.add(sprite)
    frame(stage)
    point = _rotate((2, -3), direction, 2)
    x, y = stage.to_screen(point)
    assert stage._target.get_at((round(x), round(y)))[:3] == (255, 0, 0)
    outside = _rotate((-2, 3), direction, 2)
    x, y = stage.to_screen(outside)
    assert stage._target.get_at((round(x), round(y)))[:3] == (0, 0, 0)


def test_cardinal_rotation_has_no_phantom_edge_overlap() -> None:
    """Exact cardinal transforms avoid floating-point slivers at touching AABB edges."""
    sprite = Sprite(PillowImage.new("RGBA", (10, 20)), direction=0)
    other = Sprite(PillowImage.new("RGBA", (10, 20)), direction=0, x=20)
    assert not sprite.touching(other)
    _move(sprite, 10)
    assert sprite.position == (0, 10)


def test_rotation_styles_pointing_and_bounce() -> None:
    """Visual style does not change motion; bounce validates before changing oversized actors."""
    from plocks import RotationStyle

    sprite = Sprite(PillowImage.new("RGBA", (10, 20), "red"), x=47)
    bounds = Bounds(-50, -50, 50, 50)
    assert _bounce(sprite, bounds)
    assert sprite.direction == 270 and sprite.bounds.right == 50
    sprite.rotation_style = RotationStyle.NONE
    sprite.direction = 0
    assert sprite.bounds.width == 10
    _point_towards(sprite, (sprite.x, 100))
    assert sprite.direction == 0
    _random(sprite, bounds)
    assert bounds.contains(sprite.position)
    sprite.scale = 20
    previous = (sprite.position, sprite.direction)
    with pytest.raises(ValueError):
        _bounce(sprite, bounds)
    assert (sprite.position, sprite.direction) == previous


def test_puppet_part_order_and_mirrored_pivot_pixels() -> None:
    """Attachment order controls overlap; mirroring moves pivots and image anchors together."""
    from plocks import RotationStyle

    stage = Stage(40, 40)
    stage._target = pygame.display.set_mode((40, 40))
    skeleton = Skeleton({"root": Joint(None), "hand": Joint("root", (5, 0))})
    person = Puppet(
        skeleton,
        parts={
            "root": PillowImage.new("RGBA", (20, 20), "red"),
            "hand": Image(PillowImage.new("RGBA", (4, 4), "blue"), anchor=(0, 0)),
        },
    )
    stage.add(person)
    frame(stage)
    assert stage._target.get_at((27, 22))[:3] == (0, 0, 255)
    person.rotation_style = RotationStyle.LEFT_RIGHT
    person.direction = 270
    frame(stage)
    assert stage._target.get_at((13, 22))[:3] == (0, 0, 255)
    assert stage._target.get_at((27, 22))[:3] == (255, 0, 0)
