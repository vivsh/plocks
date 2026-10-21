"""Shape factories use the ordinary immutable asset and desktop rendering path."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from pathlib import Path
from typing import cast

import pygame
import pytest

from plocks import (
    Anchor,
    Canvas,
    Event,
    Image,
    ImageGrid,
    Joint,
    Puppet,
    Skeleton,
    Sprite,
    Stage,
    TiledBackground,
    TileMap,
)


def test_shape_first_complete_path(tmp_path: Path) -> None:
    """An anchored outlined rectangle moves while its independent friend advances."""
    picture = Image.rectangle(
        24, 32, color="orange", outline="white", outline_width=2, anchor=Anchor.BOTTOM_CENTER
    )
    assert {field.name for field in fields(picture)} == {"_pixels", "_anchor"}
    assert not pygame.display.get_init() and pygame.mixer.get_init() is None
    stage = Stage(width=160, height=120)
    hero = Sprite(picture, x=-40)
    friend = Sprite(Image.rectangle(12, 12, color="skyblue"), x=40)
    stage.add(hero)
    stage.add(friend)
    hero.glide_by(x=20, seconds=0.1)

    @friend.on_update
    def move(event: Event[Sprite, float]) -> None:
        event.target.x += 20 * event.data

    @stage.on_draw
    def inspect(canvas: Canvas) -> None:
        assert stage._target is not None
        if stage.time == 0:
            assert stage._target.get_at((40, 40))[:3] == (255, 165, 0)
            assert stage._target.get_at((28, 40))[:3] == (255, 255, 255)
            assert stage._target.get_at((40, 61))[:3] == (0, 0, 0)
        if stage.time >= 0.15:
            assert hero.x == -20 and friend.x > 40
            assert stage._target.get_at((60, 40))[:3] == (255, 165, 0)
            pygame.image.save(stage._target, str(tmp_path / "shapes-first-path.png"))
            stage.stop()

    stage.run()
    assert not stage.objects and not stage._actions and stage._target is None
    assert not pygame.display.get_init()


_FACTORIES: tuple[Callable[[], Image], ...] = (
    lambda: Image.rectangle(24, 32, color="orange"),
    lambda: Image.circle(16, color="orange"),
    lambda: Image.ellipse(24, 32, color="orange"),
    lambda: Image.triangle(24, 32, color="orange"),
    lambda: Image.polygon(((0, 0), (23, 0), (12, 31)), color="orange"),
)


@pytest.mark.parametrize("factory", _FACTORIES)
def test_shapes_are_ordinary_immutable_assets(factory: Callable[[], Image]) -> None:
    """Factories add no state or native resources, and conversions cannot edit their pixels."""
    image = factory()
    assert type(image) is Image
    assert set(vars(image)) == {"_pixels", "_anchor"}
    assert not pygame.display.get_init() and pygame.mixer.get_init() is None
    before = image.to_pillow().tobytes()
    edited = image.to_pillow()
    edited.paste("blue", (0, 0, image.width, image.height))
    assert image.to_pillow().tobytes() == before
    assert Image(image)._pixels is image._pixels
    with pytest.raises(FrozenInstanceError):
        setattr(image, fields(image)[1].name, (0, 0))
    moved = image.with_anchor(Anchor.BOTTOM_CENTER)
    assert moved._pixels is image._pixels and moved.anchor == (image.width / 2, image.height)
    assert moved.resized(48, 64).anchor == (24, 64)
    assert image.flipped(horizontal=True).anchor == image.anchor
    assert image.rotated(90).width == image.height
    assert image.cropped(0, 0, 1, 1).to_pillow().getpixel((0, 0)) == image.to_pillow().getpixel(
        (0, 0)
    )


@pytest.mark.parametrize("anchor", list(Anchor) + [(2.0, -3.0)])
def test_factory_anchor_matches_file_image_convention(anchor: Anchor | tuple[float, float]) -> None:
    """Every factory resolves named and precise pivots against the final pixel dimensions."""
    images = (
        Image.rectangle(10, 20, anchor=anchor),
        Image.circle(10, anchor=anchor),
        Image.ellipse(10, 20, anchor=anchor),
        Image.triangle(10, 20, anchor=anchor),
        Image.polygon(((-5, -5), (4, -5), (-5, 14)), anchor=anchor),
    )
    for image in images:
        expected = (
            (image.width * anchor.value[0], image.height * anchor.value[1])
            if isinstance(anchor, Anchor)
            else anchor
        )
        assert image.anchor == expected


def test_shape_dimensions_orientation_and_transparent_corners() -> None:
    """Circles use diameter, ellipses use exact extents, and triangles point upward."""
    circle = Image.circle(10)
    assert (circle.width, circle.height, circle.anchor) == (20, 20, (10, 10))
    for image in (circle, Image.ellipse(30, 16)):
        pixels = image.to_pillow()
        assert pixels.getpixel((0, 0)) == (0, 0, 0, 0)
        assert pixels.getpixel((image.width // 2, image.height // 2)) == (255, 255, 255, 255)
        assert pixels.getbbox() == (0, 0, image.width, image.height)
    triangle = Image.triangle(31, 21).to_pillow()
    assert triangle.getpixel((15, 0)) == (255, 255, 255, 255)
    assert triangle.getpixel((0, 0)) == (0, 0, 0, 0)
    assert triangle.getpixel((0, 20)) == triangle.getpixel((30, 20)) == (255, 255, 255, 255)


@pytest.mark.parametrize("shape", ("rectangle", "ellipse", "triangle", "polygon", "circle"))
def test_outline_never_expands_geometry_and_keeps_independent_alpha(shape: str) -> None:
    """Fill and border are replacement colors within the original shape mask, not composited twice."""

    def make(
        color: tuple[int, int, int, int] | None, outline: tuple[int, int, int, int] | None
    ) -> Image:
        if shape == "polygon":
            return Image.polygon(
                ((0, 0), (30, 0), (30, 30), (0, 30)), color=color, outline=outline, outline_width=3
            )
        if shape == "circle":
            return Image.circle(16, color=color, outline=outline, outline_width=3)
        factory = {
            "rectangle": Image.rectangle,
            "ellipse": Image.ellipse,
            "triangle": Image.triangle,
        }[shape]
        return factory(31, 31, color=color, outline=outline, outline_width=3)

    fill, edge = (255, 0, 0, 80), (0, 0, 255, 160)
    solid, outlined, hollow = make(fill, None), make(fill, edge), make(None, edge)
    solid_pixels, outlined_pixels, hollow_pixels = (
        solid.to_pillow(),
        outlined.to_pillow(),
        hollow.to_pillow(),
    )
    assert (solid.width, solid.height) == (outlined.width, outlined.height)
    colors = {
        outlined_pixels.getpixel((x, y)) for x in range(solid.width) for y in range(solid.height)
    }
    assert fill in colors and edge in colors
    assert hollow_pixels.getpixel((solid.width // 2, solid.height // 2)) == (0, 0, 0, 0)
    for y in range(solid.height):
        for x in range(solid.width):
            original = solid_pixels.getpixel((x, y))
            result = outlined_pixels.getpixel((x, y))
            if original == (0, 0, 0, 0):
                assert result == hollow_pixels.getpixel((x, y)) == (0, 0, 0, 0)
            else:
                assert result in (fill, edge)


def test_rectangle_outline_width_and_transparent_border_color() -> None:
    """A two-pixel outline is wholly inside the requested rectangle, even with alpha zero."""
    pixels = Image.rectangle(12, 10, color="gold", outline="red", outline_width=2).to_pillow()
    assert pixels.getpixel((1, 5)) == (255, 0, 0, 255)
    assert pixels.getpixel((2, 5)) == (255, 215, 0, 255)
    transparent = Image.rectangle(12, 10, color="red", outline=(0, 0, 0, 0)).to_pillow()
    assert transparent.getpixel((0, 5)) == (0, 0, 0, 0)
    assert transparent.getpixel((5, 5)) == (255, 0, 0, 255)
    assert Image.rectangle(10, 10, color=None).to_pillow().getbbox() is None


@pytest.mark.parametrize("width,height", ((1, 1), (1, 9), (9, 1), (2, 2)))
def test_small_extents_and_oversized_outlines(width: int, height: int) -> None:
    """Small valid images remain usable and huge border widths saturate rather than overflow."""
    for factory in (Image.rectangle, Image.ellipse, Image.triangle):
        image = factory(width, height, color=None, outline="white", outline_width=1000000)
        assert (image.width, image.height) == (width, height)
        assert image.to_pillow().getbbox() is not None
        assert image.to_pillow().tobytes() == factory(width, height).to_pillow().tobytes()


def test_polygon_consumes_generator_once_translates_and_supports_concavity() -> None:
    """A negative-coordinate L shape keeps its empty corner and snapshots the iterable."""
    points = [(-3.2, -2.1), (3.9, -2.1), (3.9, 0.9), (-1.1, 0.9), (-1.1, 4.9), (-3.2, 4.9)]
    image = Image.polygon(point for point in points)
    assert (image.width, image.height) == (8, 8)
    pixels = image.to_pillow()
    assert pixels.getpixel((6, 6)) == (0, 0, 0, 0)
    assert pixels.getpixel((1, 6)) == (255, 255, 255, 255)
    points.clear()
    assert image.to_pillow().tobytes() == pixels.tobytes()
    closed = ((0.0, 0.0), (20.0, 0.0), (10.0, 10.0), (0.0, 0.0))
    assert (
        Image.polygon(closed).to_pillow().tobytes()
        == Image.polygon(closed[:-1]).to_pillow().tobytes()
    )
    assert Image.polygon(closed).width == 21
    concave = ((0.0, 0.0), (20.0, 0.0), (20.0, 6.0), (6.0, 6.0), (6.0, 20.0), (0.0, 20.0))
    border = Image.polygon(concave, color=None, outline="red", outline_width=2).to_pillow()
    assert border.getpixel((7, 7)) == (0, 0, 0, 0)
    assert border.getpixel((5, 10)) == (255, 0, 0, 255)
    assert border.getpixel((3, 10)) == (0, 0, 0, 0)


@pytest.mark.parametrize("value", (0, -1, 1.5, True, "12", float("inf")))
def test_invalid_pixel_dimensions_fail_clearly(value: object) -> None:
    """Integer-only dimensions apply equally to every factory and outline width."""
    factories: tuple[Callable[[], Image], ...] = (
        lambda: Image.rectangle(cast(int, value), 12),
        lambda: Image.ellipse(12, cast(int, value)),
        lambda: Image.triangle(cast(int, value), 12),
        lambda: Image.circle(cast(int, value)),
        lambda: Image.polygon(((0, 0), (10, 0), (0, 10)), outline_width=cast(int, value)),
    )
    error = ValueError if isinstance(value, int) and not isinstance(value, bool) else TypeError
    for factory in factories:
        with pytest.raises(error):
            factory()


@pytest.mark.parametrize(
    "points",
    (
        (),
        ((0, 0), (1, 1)),
        ((0, 0), (1, 1), (2, 2)),
        ((0, 0), (0.1, 0.1), (0.2, 0.3)),
        ((0, 0), (0, 0), (0, 0)),
    ),
)
def test_degenerate_polygons_fail_before_rasterization(
    points: tuple[tuple[float, float], ...],
) -> None:
    """There must be an area after conversion to image pixels."""
    with pytest.raises(ValueError, match="noncollinear"):
        Image.polygon(points)


@pytest.mark.parametrize("coordinate", (float("nan"), float("inf"), float("-inf")))
def test_nonfinite_points_and_anchors_are_rejected(coordinate: float) -> None:
    """Generated assets preserve finite-coordinate validation at both public boundaries."""
    with pytest.raises(ValueError):
        Image.polygon(((0, 0), (10, 0), (0, coordinate)))
    with pytest.raises(ValueError):
        Image.circle(10, anchor=(coordinate, 0))


@pytest.mark.parametrize(
    "color,error",
    (
        ("not-a-color", ValueError),
        ((-1, 0, 0), ValueError),
        ((0, 256, 0), ValueError),
        ((0, 1), ValueError),
        ((0, True, 0), TypeError),
        ((0, 1.5, 0), TypeError),
        (10, TypeError),
    ),
)
def test_invalid_colors_are_rejected_for_fill_and_outline(
    color: object, error: type[Exception]
) -> None:
    """All channels are validated and invalid outlines fail even when no fill is requested."""
    from plocks import Color

    for factory in (Image.rectangle, Image.ellipse, Image.triangle):
        with pytest.raises(error):
            factory(10, 10, color=cast(Color, color))
        with pytest.raises(error):
            factory(10, 10, color=None, outline=cast(Color, color))


def test_generated_assets_work_in_tiles_puppets_and_grids() -> None:
    """Factory output composes with existing asset consumers without geometry metadata."""
    image = Image.rectangle(16, 24, anchor=Anchor.BOTTOM_CENTER, color=(10, 20, 30))
    puppet = Puppet(Skeleton({"root": Joint(parent=None)}), parts={"root": image})
    assert (
        puppet.parts["root"] is image and puppet.bounds.width == 16 and puppet.bounds.height == 24
    )
    world = TileMap(["#"], {"#": image}, tile_size=(16, 24), solid={"#"})
    assert world.bounds.width == 16 and world.tiles_touching(world.bounds)
    assert TiledBackground(image).image is image
    frame = ImageGrid(image, frame_size=(8, 12)).frame(row=1, column=1)
    assert frame.to_pillow().getpixel((0, 0)) == (10, 20, 30, 255)
    sprite = Sprite(Image.circle(8))
    assert sprite.bounds.width == sprite.bounds.height == 16
    assert set(vars(sprite.image)) == {"_pixels", "_anchor"}
