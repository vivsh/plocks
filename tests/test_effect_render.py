"""Selected pixels specify each effect and whole-rig alpha without fragile screenshots."""

import pygame
import pytest
from PIL import Image as PillowImage

from plocks import Effect, Image, Joint, Puppet, RotationStyle, Skeleton, Sprite, Stage
from plocks._effects import _apply, _settings
from plocks._render import _assembled, frame
from plocks._runtime import close
from plocks._scripts import _step
from plocks.effects import _value


def grid(size: int = 8) -> Image:
    pixels = PillowImage.new("RGBA", (size, size))
    for y in range(size):
        for x in range(size):
            pixels.putpixel((x, y), (x * 20, y * 20, 50, 255))
    return Image(pixels)


def paint(effect: Effect, value: float, image: Image | None = None) -> pygame.Surface:
    stage = Stage()
    actor = Sprite(grid() if image is None else image)
    original = pygame.image.tobytes(actor.image._pixels, "RGBA")
    stage.add(actor)
    stage._state = "running"
    try:
        actor.set_effect(effect, value)
        _step(stage)
        result = _apply(actor.image._pixels, actor)
        assert result.get_size() == actor.image._pixels.get_size()
        assert pygame.image.tobytes(actor.image._pixels, "RGBA") == original
        return result
    finally:
        close(stage)


def test_hue_brightness_and_alpha() -> None:
    red = Image.rectangle(3, 3, color=(255, 0, 0, 128))
    color = paint(Effect.COLOR, 200 / 3, red).get_at((1, 1))
    assert color.g >= 250 and color.r <= 5 and color.b <= 5 and color.a == 128
    brighter = paint(Effect.BRIGHTNESS, 50, Image.rectangle(3, 3, color=(0, 0, 0, 100)))
    assert brighter.get_at((1, 1))[:] == (128, 128, 128, 100)
    assert paint(Effect.BRIGHTNESS, -100, red).get_at((1, 1))[:] == (0, 0, 0, 128)
    assert paint(Effect.GHOST, 50, red).get_at((1, 1)).a == pytest.approx(64, abs=1)


def test_mosaic_repeats_and_pixelate_groups_pixels() -> None:
    mosaic = paint(Effect.MOSAIC, 10)
    assert mosaic.get_at((0, 0)) == mosaic.get_at((4, 4))
    assert mosaic.get_at((0, 0))[:2] == (20, 20)
    assert mosaic.get_at((3, 3))[:2] == (140, 140)
    chunky = paint(Effect.PIXELATE, 20)
    assert all(chunky.get_at((x, y))[:] == (20, 20, 50, 255) for x in (0, 1) for y in (0, 1))
    assert chunky.get_at((2, 2))[:] == (60, 60, 50, 255)
    assert pygame.image.tobytes(chunky, "RGBA") == pygame.image.tobytes(
        paint(Effect.PIXELATE, -20), "RGBA"
    )


def test_fisheye_bulges_and_whirl_twists_source_coordinates() -> None:
    bulge = paint(Effect.FISHEYE, 100, grid(9))
    assert bulge.get_at((4, 4))[:] == (80, 80, 50, 255)
    assert bulge.get_at((6, 4))[:] == (100, 80, 50, 255)
    twisted = paint(Effect.WHIRL, 180)
    assert twisted.get_at((5, 3))[:] == (80, 40, 50, 255)
    reverse = paint(Effect.WHIRL, -180)
    assert reverse.get_at((5, 3)) != twisted.get_at((5, 3))


@pytest.mark.parametrize("effect", list(Effect))
def test_transparent_images_remain_transparent(effect: Effect) -> None:
    output = paint(effect, 80, Image.rectangle(7, 5, color=(0, 0, 0, 0)))
    assert all(output.get_at((x, y)).a == 0 for x in range(7) for y in range(5))


def test_noop_values_reuse_source_and_extreme_finite_amounts_are_safe() -> None:
    actor = Sprite(grid())
    actor._effects = {Effect.COLOR: 0, Effect.MOSAIC: 1, Effect.PIXELATE: 4}
    assert _settings(actor) == {} and _apply(actor.image._pixels, actor) is actor.image._pixels
    for effect in Effect:
        output = paint(effect, 1e308)
        assert output.get_size() == (8, 8)


def puppet() -> Puppet:
    skeleton = Skeleton({"root": Joint(None), "overlay": Joint("root")})
    return Puppet(
        skeleton,
        parts={
            "root": Image.rectangle(10, 10, color="red"),
            "overlay": Image.rectangle(10, 10, color="blue"),
        },
    )


def test_puppet_ghost_applies_once_after_overlapping_parts() -> None:
    stage = Stage(background="black")
    person = puppet()
    stage.add(person)
    stage._state = "running"
    try:
        person.set_effect(Effect.GHOST, 50)
        _step(stage)
        pygame.display.init()
        stage._target = pygame.display.set_mode((stage.width, stage.height))
        frame(stage)
        assert stage._target.get_at((stage.width // 2, stage.height // 2))[:3] == (0, 0, 128)
        assembled, anchor = _assembled(person)
        assert assembled.get_at((5, 5))[:] == (0, 0, 255, 255) and anchor == (5, 5)
    finally:
        close(stage)


def test_puppet_effects_follow_pose_parts_camera_mirroring_and_keep_bounds() -> None:
    stage = Stage(background="black")
    skeleton = Skeleton({"root": Joint(None), "arm": Joint("root", offset=(12, 0))})
    person = Puppet(skeleton, parts={"root": grid(), "arm": Image.rectangle(4, 8, color="red")})
    stage.add(person)
    stage._state = "running"
    try:
        person.position = (60, 20)
        person.scale = 2
        person.rotation_style = RotationStyle.LEFT_RIGHT
        person.direction = 270
        stage.camera = (40, 0)
        person.animate_effect(Effect.GHOST, to=50, seconds=1)
        _step(stage)
        stage._tick = 30
        person.pose = person.pose.with_angles({"arm": 90})
        person.set_part_image("root", Image.rectangle(8, 8, color="green"))
        _step(stage)
        before = person.bounds
        pygame.display.init()
        stage._target = pygame.display.set_mode((stage.width, stage.height))
        frame(stage)
        sx, sy = stage.to_screen(person.position)
        pixel = stage._target.get_at((round(sx), round(sy)))
        assert pixel.g == pytest.approx(191, abs=1)  # Green=255, ghost halfway to 50%.
        assert _value(person, Effect.GHOST) == 25 and person.bounds == before
        copy = person.clone()
        assert copy._effects == {Effect.GHOST: 25}
    finally:
        close(stage)


def test_combined_color_brightness_and_ghost_order() -> None:
    stage = Stage()
    image = Image.rectangle(4, 4, color=(255, 0, 0, 128))
    hero = Sprite(image)
    stage.add(hero)
    stage._state = "running"
    try:
        hero.set_effect(Effect.COLOR, 100)
        hero.set_effect(Effect.BRIGHTNESS, -50)
        hero.set_effect(Effect.GHOST, 50)
        _step(stage)
        result = _apply(image._pixels, hero)
        pixel = result.get_at((1, 1))
        assert pixel.r == 0 and pixel.g == pytest.approx(127, abs=3)
        assert pixel.b == pytest.approx(127, abs=3) and pixel.a == pytest.approx(64, abs=1)
        assert image._pixels.get_at((1, 1))[:] == (255, 0, 0, 128)
    finally:
        close(stage)


def test_mosaic_matches_centered_sampling_at_cell_boundaries() -> None:
    pixels = PillowImage.new("RGBA", (4, 80))
    for y in range(80):
        for x in range(4):
            pixels.putpixel((x, y), (x, y, 0, 255))
    result = paint(Effect.MOSAIC, 10, Image(pixels))
    assert result.get_at((0, 1)).g == 2
    assert result.get_at((0, 6)).g == 12
