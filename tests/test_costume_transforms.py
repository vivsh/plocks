"""Immutable image operations preserve pixels, anchors, and actor placement."""

import math

import pytest
from PIL import Image as PillowImage

from plocks import Image, Joint, Puppet, Skeleton, Sprite


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
