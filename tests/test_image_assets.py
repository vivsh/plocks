"""New image names, typed loaders and anchor placement share existing execution."""

import json
from pathlib import Path

import pygame
from PIL import Image as PillowImage

from plocks import Anchor, Canvas, Event, ImageGrid, ImageMap, Sprite, Stage


def test_image_map_first_complete_path(tmp_path: Path) -> None:
    """A JSON-loaded anchored sprite changes appearance while its friend keeps moving."""
    atlas = PillowImage.new("RGBA", (32, 24), "red")
    atlas.paste("blue", (16, 0, 32, 24))
    path = tmp_path / "actors.png"
    atlas.save(path)
    path.with_suffix(".json").write_text(
        json.dumps(
            {
                "frames": {
                    "hero": {"frame": {"x": 0, "y": 0, "w": 16, "h": 24}},
                    "friend": {"frame": {"x": 16, "y": 0, "w": 16, "h": 16}},
                }
            }
        )
    )
    pictures = ImageMap(path)
    hero = Sprite(pictures["hero"].with_anchor(Anchor.BOTTOM_CENTER), x=-40)
    friend = Sprite(pictures["friend"], x=40)
    stage = Stage(width=160, height=120)
    stage.add(hero)
    stage.add(friend)
    hero.set_image(pictures["friend"], after=hero.wait(0.05))

    @friend.on_update
    def move(event: Event[Sprite, float]) -> None:
        event.target.x += 20 * event.data

    @stage.on_draw
    def inspect(canvas: Canvas) -> None:
        assert stage._target is not None
        if stage.time == 0:
            assert stage._target.get_at((40, 48))[:3] == (255, 0, 0)
            assert stage._target.get_at((40, 61))[:3] == (0, 0, 0)
        if stage.time >= 0.1:
            assert hero.image is pictures["friend"] and friend.x > 40
            assert stage._target.get_at((40, 60))[:3] == (0, 0, 255)
            pygame.image.save(stage._target, str(tmp_path / "image-map.png"))
            stage.stop()

    stage.run()
    assert not stage.objects and not stage._actions and stage._target is None
    assert ImageGrid(path, frame_size=(16, 24)).frame(
        row=0, column=0, anchor=Anchor.BOTTOM_CENTER
    ).anchor == (8, 24)
    assert not pygame.display.get_init()


import warnings
from collections.abc import Callable, Mapping
from dataclasses import fields
from typing import cast

import pytest

from plocks import AssetError, Image, Joint, Puppet, Script, Skeleton, TiledBackground
from plocks._runtime import advance, close


@pytest.mark.parametrize("anchor", list(Anchor))
def test_named_anchors_resolve_once_and_transform_with_pixels(anchor: Anchor) -> None:
    """All nine pivots use image edges and share the established transformation rules."""
    image = Image(PillowImage.new("RGBA", (32, 48)), anchor=anchor)
    x, y = anchor.value
    assert image.anchor == (32 * x, 48 * y)
    assert image.with_anchor(anchor).anchor == image.anchor
    assert image.resized(64, 96).anchor == (64 * x, 96 * y)
    assert image.flipped(horizontal=True).anchor == (32 - 32 * x, 48 * y)
    assert image.rotated(90).anchor == (48 - 48 * y, 32 * x)
    assert {field.name for field in fields(image)} == {"_pixels", "_anchor"}


def test_precise_anchor_overloads_and_immutable_source_normalization() -> None:
    """Pixels are borrowed only from already immutable assets; precise anchors stay valid."""
    pillow = PillowImage.new("RGBA", (12, 18), "red")
    image = Image(pillow, anchor=Anchor.BOTTOM_CENTER)
    copied = Image(image)
    assert copied.anchor == (6, 18) and copied._pixels is image._pixels
    assert Image(image, anchor=Anchor.TOP_LEFT).anchor == (0, 0)
    assert image.with_anchor((2, 3)).anchor == image.with_anchor(x=2, y=3).anchor == (2, 3)
    assert image.with_anchor((-20, 50)).anchor == (-20, 50)
    pillow.paste("blue", (0, 0, 12, 18))
    returned = copied.to_pillow()
    returned.paste("green", (0, 0, 12, 18))
    assert image.to_pillow().getpixel((0, 0)) == (255, 0, 0, 255)
    with pytest.raises(TypeError):
        cast(Callable[[int], Image], image.with_anchor)(2)
    with pytest.raises(ValueError):
        image.with_anchor((float("nan"), 0))


def test_grid_anchors_resolve_per_frame_not_atlas() -> None:
    """Both extraction entry points support named anchors on owned frame pixels."""
    grid = ImageGrid(PillowImage.new("RGBA", (64, 48)), frame_size=(16, 24))
    frames = grid.frames(row=1, anchor=Anchor.BOTTOM_CENTER)
    assert len(frames) == 4 and all(frame.anchor == (8, 24) for frame in frames)
    assert grid.frame(row=0, column=1, anchor=(2, 3)).anchor == (2, 3)
    assert grid.frame(row=0, column=1).anchor == (8, 12)


def test_custom_loader_called_once_and_results_snapshotted(tmp_path: Path) -> None:
    """A loader owns its parsing; ImageMap retains only a read-only named-asset snapshot."""
    source = Image(PillowImage.new("RGBA", (32, 48)))
    calls: list[Image] = []
    values: dict[str, Image] = {}
    metadata = tmp_path / "pictures.csv"
    metadata.write_text("hero,0,0,12,24\ntree,12,0,20,48\n")

    def custom(atlas: Image) -> Mapping[str, Image]:
        calls.append(atlas)
        for line in metadata.read_text().splitlines():
            name, x, y, width, height = line.split(",")
            values[name] = atlas.cropped(int(x), int(y), int(width), int(height)).with_anchor(
                Anchor.BOTTOM_CENTER
            )
        return values

    pictures = ImageMap(source, metadata=custom)
    assert calls == [source] and tuple(pictures) == ("hero", "tree") and len(pictures) == 2
    assert pictures["tree"] is values["tree"] and pictures["tree"].anchor == (10, 48)
    saved = pictures["hero"]
    values.clear()
    assert pictures["hero"] is saved and len(pictures) == 2
    assert {field.name for field in fields(ImageMap)} == {"_images"}
    assert pictures.get("missing") is None
    with pytest.raises(KeyError):
        _ = pictures["missing"]
    with pytest.raises(TypeError):
        cast(dict[str, Image], pictures._images)["new"] = source
    with pytest.raises(ValueError, match="explicit metadata"):
        ImageMap(source)


def test_custom_loader_exception_keeps_identity_and_traceback() -> None:
    """Game-specific parsing errors remain directly diagnosable rather than being wrapped."""
    failure = LookupError("custom file failed")

    def custom(atlas: Image) -> Mapping[str, Image]:
        raise failure

    with pytest.raises(LookupError) as caught:
        ImageMap(PillowImage.new("RGBA", (1, 1)), metadata=custom)
    assert caught.value is failure and failure.__traceback__ is not None
    assert any("ImageMap" in note for note in failure.__notes__)


@pytest.mark.parametrize("value", [None, [], {}, {"": None}, {"hero": (0, 0, 1, 1)}])
def test_custom_loader_invalid_results_fail_without_publishing(value: object) -> None:
    """Untyped loaders must still return a nonempty named collection of real Images."""

    def custom(atlas: Image) -> Mapping[str, Image]:
        return cast(Mapping[str, Image], value)

    with pytest.raises((ValueError, TypeError)):
        ImageMap(PillowImage.new("RGBA", (1, 1)), metadata=custom)


def write_atlas(tmp_path: Path, **entry: object) -> Path:
    """An ordinary single-image JSON Hash fixture, with explicit packing flags."""
    path = tmp_path / "sprites.png"
    PillowImage.new("RGBA", (20, 30), "red").save(path)
    data = {
        "frames": {"hero.png": {"frame": {"x": 2, "y": 3, "w": 12, "h": 18}, **entry}},
        "meta": {"size": {"w": 20, "h": 30}, "scale": "1"},
    }
    path.with_suffix(".json").write_text(json.dumps(data))
    return path


def test_json_hash_paths_and_exact_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Default JSON follows the image path; explicit metadata retains cwd-relative semantics."""
    path = write_atlas(
        tmp_path,
        rotated=False,
        trimmed=False,
        sourceSize={"w": 12, "h": 18},
        spriteSourceSize={"x": 0, "y": 0, "w": 12, "h": 18},
    )
    pictures = ImageMap(path)
    assert tuple(pictures) == ("hero.png",) and pictures["hero.png"].anchor == (6, 9)
    assert (pictures["hero.png"].width, pictures["hero.png"].height) == (12, 18)
    elsewhere = tmp_path / "other"
    elsewhere.mkdir()
    metadata = elsewhere / "custom.json"
    metadata.write_bytes(path.with_suffix(".json").read_bytes())
    monkeypatch.chdir(elsewhere)
    assert tuple(ImageMap(path, metadata="custom.json")) == ("hero.png",)
    assert not pygame.display.get_init()


@pytest.mark.parametrize(
    "entry",
    [
        {"rotated": True},
        {"trimmed": True},
        {"rotated": "false"},
        {"frame": {"x": 19, "y": 0, "w": 2, "h": 2}},
        {"frame": {"x": 0, "y": 0, "w": 0, "h": 2}},
        {"frame": {"x": True, "y": 0, "w": 2, "h": 2}},
        {"sourceSize": {"w": 1, "h": 1}},
        {"spriteSourceSize": {"x": 1, "y": 0, "w": 12, "h": 18}},
    ],
)
def test_bad_or_unsupported_rectangles_are_actionable(
    tmp_path: Path, entry: dict[str, object]
) -> None:
    """No incorrect crop or pivot is silently accepted from unsupported packing metadata."""
    path = write_atlas(tmp_path, **entry)
    with pytest.raises(AssetError, match="sprites.json"):
        ImageMap(path)


@pytest.mark.parametrize(
    "meta", [{"size": {"w": 1, "h": 1}}, {"scale": "0.5"}, {"related_multi_packs": ["other.json"]}]
)
def test_mismatched_or_multiple_atlases_fail(tmp_path: Path, meta: dict[str, object]) -> None:
    """A single-image importer cannot quietly accept a different image size or pack."""
    path = write_atlas(tmp_path)
    document = json.loads(path.with_suffix(".json").read_text())
    document["meta"] = meta
    path.with_suffix(".json").write_text(json.dumps(document))
    with pytest.raises(AssetError):
        ImageMap(path)


def test_duplicate_json_keys_and_missing_files(tmp_path: Path) -> None:
    """Duplicate names, malformed documents and missing companion files report asset errors."""
    path = write_atlas(tmp_path)
    path.with_suffix(".json").write_text('{"frames":{"hero":{},"hero":{}}}')
    with pytest.raises(AssetError, match="Duplicate"):
        ImageMap(path)
    path.with_suffix(".json").write_text("not JSON")
    with pytest.raises(AssetError):
        ImageMap(path)
    path.with_suffix(".json").unlink()
    with pytest.raises(AssetError):
        ImageMap(path)


def test_deprecated_assets_remain_exact_aliases() -> None:
    """Legacy constructor access warns without introducing another type or pixel owner."""
    import plocks
    from plocks import imaging

    with pytest.warns(DeprecationWarning, match="use Image"):
        assert plocks.Costume is Image
    with pytest.warns(DeprecationWarning, match="use ImageGrid"):
        assert plocks.SpriteSheet is ImageGrid
    with pytest.warns(DeprecationWarning, match="use Image"):
        assert imaging.Costume is Image
    with pytest.raises(AttributeError):
        getattr(plocks, "not_an_asset" + "_name")


def test_legacy_methods_share_immediate_state_actions_and_writer_cancellation() -> None:
    """Old names forward to the canonical API, including generic scripts and part edits."""
    image = Image(PillowImage.new("RGBA", (8, 8), "red"))
    blue = Image(PillowImage.new("RGBA", (8, 8), "blue"))
    stage = Stage()
    hero = Sprite(image)
    puppet = Puppet(Skeleton({"root": Joint(None)}), parts={"root": image})
    background = TiledBackground(image)
    for obj in (hero, puppet, background):
        stage.add(obj)
    stage._state, stage._last_wall = "running", 0
    try:
        with pytest.warns(DeprecationWarning):
            assert hero.costume is image
        with pytest.warns(DeprecationWarning):
            hero.costume = blue
        assert hero.image is blue
        with pytest.warns(DeprecationWarning):
            action = hero.set_costume(image)
        with pytest.warns(DeprecationWarning):
            animation = hero.costumes((image, blue), durations=(0.05, 0.05), after=action)
        advance(stage, 1 / 60)
        assert action.done
        hero.image = blue
        assert animation.cancelled
        with pytest.warns(DeprecationWarning):
            script = Script(Sprite).set_costume(image).costumes((image,), fps=10)
        with pytest.warns(DeprecationWarning):
            parts = Script(Puppet).set_part_costume("root", blue)
        hero.act(script)
        puppet.act(parts)
        with pytest.warns(DeprecationWarning):
            background.costume = blue
        with pytest.warns(DeprecationWarning):
            assert background.costume is background.image
        advance(stage, 2 / 60)
        assert puppet.parts["root"] is blue
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter("always")
            hero.image = blue
            hero.set_image(image)
            hero.images((image,), fps=10)
            puppet.set_part_image("root", image)
        assert not seen
    finally:
        close(stage)


def test_pixelorama_named_anchor_keeps_authored_timing() -> None:
    """The enum resolves per frame without changing Pixelorama tags or durations."""
    from plocks import PixeloramaSheet

    path = Path(__file__).parent / "fixtures/games/integrations_proof/assets/hero.png"
    art = PixeloramaSheet(path, anchor=Anchor.BOTTOM_CENTER)
    assert art.durations == (0.1, 0.2, 0.1) and art.animations == ("walk",)
    assert all(image.anchor == (16, 40) for image in art.frames)


def test_async_custom_loader_is_rejected_without_leaking_coroutine() -> None:
    """Untyped async loaders fail synchronously and their unused coroutine is closed."""
    import gc

    async def custom(atlas: Image) -> Mapping[str, Image]:
        return {"image": atlas}

    invalid = cast(Callable[[Image], Mapping[str, Image]], custom)
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        with pytest.raises(TypeError, match="synchronous"):
            ImageMap(PillowImage.new("RGBA", (1, 1)), metadata=invalid)
        gc.collect()
    assert not seen


def test_legacy_star_imports_resolve_identity_aliases() -> None:
    """The explicit export lists keep old constructor names available to existing code."""
    namespace: dict[str, object] = {}
    with pytest.warns(DeprecationWarning):
        exec("from plocks import *", namespace)  # noqa: S102 -- fixed import tests legacy Python semantics
    assert namespace["Costume"] is namespace["Image"] is Image
    assert namespace["SpriteSheet"] is namespace["ImageGrid"] is ImageGrid
