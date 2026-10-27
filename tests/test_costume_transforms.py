"""Immutable image operations preserve pixels, anchors, and actor placement."""

import math

import pygame
import pytest
from PIL import Image as PillowImage

from plocks import Anchor, Color, Image, Joint, Puppet, Skeleton, Sprite, Stage
from plocks._render import frame
from plocks._runtime import close


def sample() -> Image:
    """An asymmetric image makes both axis flips and rotation observable."""
    image = PillowImage.new("RGBA", (3, 2))
    for y in range(2):
        for x in range(3):
            image.putpixel((x, y), (10 + x + 3 * y, 0, 0, 255))
    return Image(image, anchor=(0.5, 1.5))


@pytest.mark.parametrize("horizontal,vertical", [(True, False), (False, True), (True, True)])
def test_flipped_pixels_and_anchor(horizontal: bool, vertical: bool) -> None:
    source = sample()
    result = source.flipped(horizontal=horizontal, vertical=vertical)
    assert result.anchor == (2.5 if horizontal else 0.5, 0.5 if vertical else 1.5)
    for y in range(2):
        for x in range(3):
            assert result.to_pillow().getpixel((x, y)) == source.to_pillow().getpixel(
                (2 - x if horizontal else x, 1 - y if vertical else y)
            )
    restored = result.flipped(horizontal=horizontal, vertical=vertical)
    assert restored.to_pillow().tobytes() == source.to_pillow().tobytes()
    assert restored.anchor == source.anchor
    assert source.flipped() is source


def test_crop_keeps_attachment_and_owns_pixels() -> None:
    source = sample()
    result = source.cropped(x=1, y=0, width=2, height=1)
    assert (result.width, result.height, result.anchor) == (2, 1, (-0.5, 1.5))
    assert result.to_pillow().getpixel((0, 0)) == (11, 0, 0, 255)
    assert result._pixels is not source._pixels
    exported = result.to_pillow()
    exported.putpixel((0, 0), (0, 0, 0, 0))
    assert result.to_pillow().getpixel((0, 0)) == (11, 0, 0, 255)
    assert source.anchor == (0.5, 1.5)


def test_anchor_shares_pixels_without_changing_source() -> None:
    source = sample()
    result = source.with_anchor(x=-5, y=10)
    assert result._pixels is source._pixels
    assert result.anchor == (-5, 10)
    assert source.anchor == (0.5, 1.5)
    result.to_pillow().paste("black", (0, 0, 3, 2))
    assert source.to_pillow().getpixel((0, 0)) == (10, 0, 0, 255)


def test_resize_uses_nearest_neighbor_and_scales_anchor() -> None:
    source = sample()
    result = source.resized(width=6, height=6)
    assert result.anchor == (1, 4.5)
    for y in range(6):
        for x in range(6):
            assert result.to_pillow().getpixel((x, y)) == source.to_pillow().getpixel(
                (x // 2, y // 3)
            )
    assert (source.width, source.height) == (3, 2)


@pytest.mark.parametrize("degrees", [90.0, -270.0, 450.0])
def test_clockwise_rotation_expands_and_transforms_anchor(degrees: float) -> None:
    source = sample()
    result = source.rotated(degrees)
    assert (result.width, result.height, result.anchor) == (2, 3, (0.5, 0.5))
    for y in range(2):
        for x in range(3):
            assert result.to_pillow().getpixel((1 - y, x)) == source.to_pillow().getpixel((x, y))
    restored = result.rotated(-90)
    assert restored.anchor == source.anchor
    assert restored.to_pillow().tobytes() == source.to_pillow().tobytes()


def test_oblique_rotation_keeps_center_and_transparent_padding() -> None:
    source = Image(PillowImage.new("RGBA", (12, 8), "red"))
    result = source.rotated(30)
    assert result.width >= math.ceil(12 * math.cos(math.pi / 6) + 8 * 0.5)
    assert result.height >= math.ceil(12 * 0.5 + 8 * math.cos(math.pi / 6))
    assert result.anchor == (result.width / 2, result.height / 2)
    assert result.to_pillow().getpixel((0, 0)) == (0, 0, 0, 0)
    offset = source.with_anchor(x=3, y=2).rotated(30)
    assert offset.anchor == pytest.approx(
        (
            result.width / 2 - 3 * math.cos(math.pi / 6) + 1,
            result.height / 2 - 1.5 - 2 * math.cos(math.pi / 6),
        )
    )


def test_transformed_image_places_sprites_and_puppet_parts() -> None:
    image = sample().flipped(horizontal=True).resized(width=6, height=4)
    sprite = Sprite(image)
    puppet = Puppet(Skeleton({"root": Joint(None)}), parts={"root": image})
    assert sprite.bounds == puppet.bounds
    assert (sprite.bounds.left, sprite.bounds.top) == (-5, 3)
    puppet = Puppet(puppet.skeleton, parts={"root": image.with_anchor(x=0, y=0)})
    assert (puppet.bounds.left, puppet.bounds.top) == (0, 0)


@pytest.mark.parametrize(
    "x,y,width,height",
    [(-1, 0, 1, 1), (0, -1, 1, 1), (0, 0, 0, 1), (0, 0, 1, -1), (2, 0, 2, 1), (0, 1, 1, 2)],
)
def test_invalid_crops(x: int, y: int, width: int, height: int) -> None:
    with pytest.raises(ValueError):
        sample().cropped(x, y, width, height)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_geometry(value: float) -> None:
    with pytest.raises(ValueError):
        sample().rotated(value)
    with pytest.raises(ValueError):
        sample().with_anchor(x=value, y=0)
    with pytest.raises(ValueError):
        sample().with_anchor(x=0, y=value)


def test_invalid_sizes_and_boolean_numbers() -> None:
    with pytest.raises(ValueError):
        sample().resized(0, 2)
    with pytest.raises(ValueError):
        sample().resized(2, -1)
    with pytest.raises(TypeError):
        sample().resized(True, 2)
    with pytest.raises(TypeError):
        sample().cropped(True, 0, 1, 1)
    with pytest.raises(TypeError):
        sample().rotated(True)
    with pytest.raises(ValueError):
        sample().with_anchor(x=1e308, y=0).resized(300, 2)


@pytest.mark.parametrize("anchor", [(4, 6), (3.5, 5.5), (-1, 8)])
@pytest.mark.parametrize("scale", [1, 2])
def test_trimmed_sprite_keeps_visible_pixels_in_place(
    anchor: tuple[float, float], scale: float
) -> None:
    """Trimming a ready-made asset tightens bounds without shifting rendered artwork."""
    pixels = PillowImage.new("RGBA", (8, 6), (200, 100, 50, 0))
    pixels.paste((220, 20, 50, 255), (2, 1, 6, 4))
    image = Image(pixels, anchor=anchor)
    stage = Stage(24, 24)
    hero = Sprite(image, x=2, y=3, scale=scale)
    stage.add(hero)
    stage._target = pygame.display.set_mode((24, 24))
    try:
        frame(stage)
        before = pygame.image.tobytes(stage._target, "RGBA")
        hero.image = image.trimmed()
        frame(stage)
        assert pygame.image.tobytes(stage._target, "RGBA") == before
        assert (hero.image.width, hero.image.height) == (4, 3)
        assert hero.image.anchor == (anchor[0] - 2, anchor[1] - 1)
        assert hero.position == (2, 3) and image.anchor == anchor
        assert (image.width, image.height) == (8, 6)
    finally:
        close(stage)


@pytest.mark.parametrize("color", ["white", "#ffffff", (255, 255, 255), (255, 255, 255, 255)])
def test_trimmed_chosen_color_removes_only_outer_padding(color: Color) -> None:
    """Equivalent color spellings trim opaque padding without deleting an interior white hole."""
    pixels = PillowImage.new("RGBA", (9, 7), "white")
    pixels.paste("red", (2, 1, 7, 6))
    pixels.putpixel((4, 3), (255, 255, 255, 255))
    source = Image(pixels, anchor=(4.5, 7))
    result = source.trimmed(color=color)
    assert (result.width, result.height, result.anchor) == (5, 5, (2.5, 6))
    assert result.to_pillow().getpixel((2, 2)) == (255, 255, 255, 255)
    assert result.to_pillow().getpixel((0, 0)) == (255, 0, 0, 255)
    assert source.to_pillow().tobytes() == pixels.tobytes()
    assert result._pixels is not source._pixels
    exported = result.to_pillow()
    exported.paste("blue", (0, 0, 5, 5))
    assert result.to_pillow().getpixel((0, 0)) == (255, 0, 0, 255)
    assert result.trimmed(color=color) is result


def test_trimmed_preserves_faint_pixels_and_ignores_hidden_rgb() -> None:
    """All nonzero alpha counts, even one; hidden RGB and transparent interior gaps survive the crop."""
    pixels = PillowImage.new("RGBA", (7, 5), (255, 10, 70, 0))
    pixels.putpixel((1, 1), (5, 10, 15, 1))
    pixels.putpixel((5, 3), (30, 40, 50, 255))
    result = Image(pixels).trimmed()
    assert (result.width, result.height) == (5, 3)
    assert result.to_pillow().getpixel((0, 0)) == (5, 10, 15, 1)
    assert result.to_pillow().getpixel((1, 1)) == (255, 10, 70, 0)


def test_trimmed_color_matches_rgba_exactly_with_no_tolerance() -> None:
    """A one-channel or alpha difference stays visible, even at alpha one."""
    pixels = PillowImage.new("RGBA", (7, 5), (255, 255, 255, 255))
    pixels.putpixel((1, 1), (255, 255, 255, 1))
    pixels.putpixel((5, 3), (254, 255, 255, 255))
    result = Image(pixels).trimmed(color="white")
    assert (result.width, result.height) == (5, 3)
    assert result.to_pillow().getpixel((0, 0)) == (255, 255, 255, 1)
    assert result.to_pillow().getpixel((4, 2)) == (254, 255, 255, 255)
    pixels.paste((20, 40, 60, 128), (0, 0, 7, 5))
    pixels.putpixel((3, 2), (20, 40, 60, 127))
    result = Image(pixels).trimmed(color=(20, 40, 60, 128))
    assert (result.width, result.height) == (1, 1)
    assert result.to_pillow().getpixel((0, 0)) == (20, 40, 60, 127)


def test_trimmed_combines_color_with_transparency_and_anchor_choices() -> None:
    """A mixed border trims both transparent and matching-color pixels; reanchoring is explicit."""
    pixels = PillowImage.new("RGBA", (8, 8), (70, 30, 10, 0))
    pixels.paste("white", (1, 1, 7, 7))
    pixels.paste("blue", (3, 2, 5, 6))
    result = Image(pixels, anchor=Anchor.BOTTOM_CENTER).trimmed(color="white")
    assert (result.width, result.height, result.anchor) == (2, 4, (1, 6))
    assert result.with_anchor(Anchor.BOTTOM_CENTER).anchor == (1, 4)
    assert result.resized(4, 8).anchor == (2, 12)
    flipped = result.flipped(horizontal=True)
    assert flipped.trimmed() is flipped and flipped.anchor == (1, 6)


@pytest.mark.parametrize("color", [None, "white"])
def test_trimmed_empty_or_unchanged_images_reuse_the_asset(color: Color | None) -> None:
    """No-content and no-crop cases retain valid dimensions, anchor and identity instead of a zero-size image."""
    for fill in ((255, 255, 255, 0), "white", "red"):
        source = Image(PillowImage.new("RGBA", (3, 2), fill), anchor=(-2, 5))
        assert source.trimmed(color=color) is source


@pytest.mark.parametrize("color", ["not a color", (-1, 0, 0), (256, 0, 0)])
def test_trimmed_invalid_colors_fail_without_mutation(color: Color) -> None:
    """Invalid names/channels fail even if there is nothing to crop, leaving the original intact."""
    source = sample()
    before = source.to_pillow().tobytes()
    with pytest.raises(ValueError):
        source.trimmed(color=color)
    assert source.to_pillow().tobytes() == before and source.anchor == (0.5, 1.5)
