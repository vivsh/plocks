"""Real editor fixtures, timing contracts, layer geometry and portable references."""

import base64
import gzip
import json
import shutil
import struct
import zlib
from pathlib import Path
from typing import cast

import pygame
import pytest
from PIL import Image as PillowImage

from plocks import AssetError, Bounds, Image, PixeloramaSheet, Sprite, Stage, TiledMap, TileMap
from plocks._asset_json import _document
from plocks._render import _tiles
from plocks._runtime import advance, close

FIXTURES = Path(__file__).parent / "fixtures"
ART = FIXTURES / "games/integrations_proof/assets"


def game(tmp_path: Path) -> Path:
    shutil.copytree(ART, tmp_path / "assets")
    return tmp_path / "assets"


def save(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data))


def ticks(stage: Stage, count: int) -> None:
    for _ in range(count):
        advance(stage, (stage._last_wall or 0.0) + 1 / stage.tick_rate)


def test_real_pixelorama_tag_timing_and_immutable_pixels(tmp_path: Path) -> None:
    assets = game(tmp_path)
    sheet = PixeloramaSheet(assets / "hero.png", anchor=(3, 7))
    assert sheet.animations == ("walk",) and sheet.durations == (0.1, 0.2, 0.1)
    assert [frame.anchor for frame in sheet.frames] == [(3, 7)] * 3
    assert [
        cast(tuple[int, ...], frame.to_pillow().getpixel((0, 0)))[:3] for frame in sheet.frames
    ] == [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
    ]
    original = sheet.frames[0].to_pillow().tobytes()
    PillowImage.new("RGBA", (96, 40), "black").save(assets / "hero.png")
    assert sheet.frames[0].to_pillow().tobytes() == original
    returned = sheet.frames[0].to_pillow()
    returned.putpixel((0, 0), (1, 2, 3, 4))
    assert sheet.frames[0].to_pillow().tobytes() == original
    with pytest.raises(KeyError):
        sheet.animation("absent")
    with pytest.raises(AttributeError):
        sheet._durations = (1,)  # type: ignore[misc]


def test_variable_image_frames_final_hold_and_conflict() -> None:
    sheet = PixeloramaSheet(ART / "hero.png")
    stage = Stage()
    one, two = Sprite(sheet.frames[0]), Sprite(sheet.frames[0])
    stage.add(one)
    stage.add(two)
    stage._state, stage._last_wall = "running", 0.0
    recipe = sheet.animation("walk")
    first, second = one.act(recipe), two.act(recipe)
    recipe.move(900)
    ticks(stage, 6)
    assert one.image is sheet.frames[1] and two.image is sheet.frames[1]
    one.image = sheet.frames[0]
    assert first.cancelled
    ticks(stage, 12)
    assert two.image is sheet.frames[2] and not second.done
    ticks(stage, 7)
    assert second.done and two.image is sheet.frames[2] and two.x == 0
    close(stage)


def test_fractional_duration_repeats_and_freeze() -> None:
    sheet = PixeloramaSheet(ART / "hero.png")
    stage = Stage()
    actor = Sprite(sheet.frames[0])
    stage.add(actor)
    stage._state, stage._last_wall = "running", 0.0
    recipe = actor.repeat(10).images(sheet.frames[:2], durations=(0.0125, 0.0375)).move(7)
    action = actor.act(recipe)
    ticks(stage, 31)
    assert action.done and actor.x == 70
    loop = actor.act(sheet.animation().repeat())
    ticks(stage, 8)
    before = actor.image
    stage.pause()
    ticks(stage, 10)
    assert actor.image is before
    stage.resume()
    ticks(stage, 1)
    loop.cancel()
    frozen = actor.image
    ticks(stage, 10)
    assert actor.image is frozen
    close(stage)


@pytest.mark.parametrize("durations", [(0.1,), (0.1, 0), (0.1, -1), (0.1, float("inf"))])
def test_invalid_variable_timing_is_rejected(durations: tuple[float, ...]) -> None:
    sheet = PixeloramaSheet(ART / "hero.png")
    actor = Sprite(sheet.frames[0])
    with pytest.raises(ValueError):
        actor.images(sheet.frames[:2], durations=durations)


@pytest.mark.parametrize(
    "field,value",
    [("direction", "1"), ("split_layers", "true"), ("resize", "200"), ("orientation", "2")],
)
def test_pixelorama_unsupported_presets_fail(tmp_path: Path, field: str, value: str) -> None:
    assets = game(tmp_path)
    data = _document(assets / "hero.json")
    cast(dict[str, object], data["export_profile"])[field] = value
    save(assets / "hero.json", data)
    with pytest.raises(AssetError, match=field if field != "orientation" else "Rows or Columns"):
        PixeloramaSheet(assets / "hero.png")


def test_actual_tiled_marker_and_matrix_mutation() -> None:
    imported = TiledMap(ART / "jungle.tmj", x=-160, y=64)
    assert imported.points["Spawns/player_start"] == (-100, -44)
    ground = imported.layers["Ground"]
    assert ground.get_tile(row=4, column=0) == "1"
    assert imported.bounds == Bounds(-160, -96, 160, 64)
    grid = TileMap(
        [["ground", None]], {"ground": ART / "ground.png"}, tile_size=(32, 32), solid={"ground"}
    )
    grid.set_tile(row=0, column=1, tile="ground")
    assert grid.cells == (("ground", "ground"),)
    with pytest.raises(ValueError):
        grid.parallax = (0.5, 1)
    assert grid.parallax == (1, 1)
    with pytest.raises(TypeError):
        imported.layers["other"] = ground  # type: ignore[index]


@pytest.mark.parametrize("compression", ["", "zlib", "gzip"])
def test_tiled_encoded_data_matches_integer_array(tmp_path: Path, compression: str) -> None:
    assets = game(tmp_path)
    path = assets / "jungle.tmj"
    data = _document(path)
    layer = cast(list[dict[str, object]], data["layers"])[0]
    values = cast(list[int], layer["data"])
    raw = struct.pack(f"<{len(values)}I", *values)
    packed = (
        zlib.compress(raw)
        if compression == "zlib"
        else gzip.compress(raw)
        if compression == "gzip"
        else raw
    )
    layer.update(data=base64.b64encode(packed).decode(), encoding="base64", compression=compression)
    save(path, data)
    result = TiledMap(path)
    assert result.layers["Ground"].cells[-1] == ("1",) * 10
    layer["data"] = base64.b64encode(packed + b"trailing").decode()
    save(path, data)
    with pytest.raises(AssetError):
        TiledMap(path)


def test_all_eight_transforms_match_real_tiled_reference() -> None:
    level = TiledMap(FIXTURES / "editors/flips.tmj")
    stage = Stage(128, 16)
    stage.camera = (64, -8)
    target = pygame.Surface((128, 16), pygame.SRCALPHA)
    _tiles(stage, target, level.layers["Tiles"])
    reference = PillowImage.open(FIXTURES / "editors/flips-reference.png").convert("RGBA")
    for column in range(8):
        for x, y in [(2, 2), (13, 2), (2, 13), (13, 13)]:
            assert tuple(target.get_at((column * 16 + x, y))) == reference.getpixel(
                (column * 16 + x, y)
            )


def test_nested_layers_markers_opacity_parallax_and_solids(tmp_path: Path) -> None:
    assets = game(tmp_path)
    path = assets / "jungle.tmj"
    data = _document(path)
    tile, objects = cast(list[dict[str, object]], data["layers"])
    tile.update(offsetx=3, offsety=4, opacity=0.5, parallaxx=0.5)
    cast(list[dict[str, object]], objects["objects"]).append(
        {"name": "zone", "x": 0, "y": 10, "width": 20, "height": 30}
    )
    data["layers"] = [
        {
            "name": "World",
            "type": "group",
            "offsetx": 10,
            "offsety": 20,
            "opacity": 0.5,
            "parallaxx": 0.5,
            "layers": [tile, objects],
        }
    ]
    save(path, data)
    level = TiledMap(path, x=-100, y=100, layer=4)
    ground = level.layers["World/Ground"]
    assert ground.position == (-87, 76) and ground.opacity == 0.25 and ground.parallax == (0.25, 1)
    assert ground.layer == 4 and level.regions["World/Spawns/zone"] == Bounds(-90, 40, -70, 70)
    assert level.points["World/Spawns/player_start"] == (-30, -28)
    tile["properties"] = [{"name": "solid", "type": "bool", "value": True}]
    save(path, data)
    with pytest.raises(AssetError, match="solid maps"):
        TiledMap(path)


def test_opacity_parallax_culling_and_original_pixels() -> None:
    image = Image(FIXTURES / "editors/corners.png")
    grid = TileMap(["x"], {"x": image}, tile_size=(16, 16), parallax=(0, 0), opacity=0.5)
    stage = Stage(64, 32)
    stage.camera = (100, 100)
    target = pygame.Surface((64, 32))
    target.fill("black")
    _tiles(stage, target, grid)
    pixel = target.get_at((34, 18))
    assert abs(pixel.r - 128) <= 1 and pixel.g == 0 and pixel.b == 0
    assert image.to_pillow().getpixel((2, 2)) == (255, 0, 0, 255)
    assert grid.bounds == Bounds(0, -16, 16, 0)


def test_solid_tile_override_uses_existing_physics(tmp_path: Path) -> None:
    assets = game(tmp_path)
    path = assets / "jungle.tmj"
    data = _document(path)
    layer = cast(list[dict[str, object]], data["layers"])[0]
    layer["properties"] = [{"name": "solid", "type": "bool", "value": True}]
    save(path, data)
    world = TiledMap(path, x=-160, y=64)
    stage = Stage(physics=True)
    stage.add(world.layers["Ground"])
    actor = Sprite(ART / "hero.png", x=-100, y=20)
    stage.add(actor)
    stage._state, stage._last_wall = "running", 0.0
    ticks(stage, 120)
    assert actor.body.grounded and actor.y == pytest.approx(-44, abs=0.3)
    close(stage)


@pytest.mark.parametrize(
    "change", ["infinite", "orientation", "image layer", "unknown GID", "duplicate name"]
)
def test_unsupported_tiled_features_fail_clearly(tmp_path: Path, change: str) -> None:
    assets = game(tmp_path)
    path = assets / "jungle.tmj"
    data = _document(path)
    layers = cast(list[dict[str, object]], data["layers"])
    if change == "infinite":
        data["infinite"] = True
    elif change == "orientation":
        data["orientation"] = "isometric"
    elif change == "image layer":
        layers.append({"type": "imagelayer", "name": "Photo"})
    elif change == "unknown GID":
        cast(list[int], layers[0]["data"])[0] = 99
    else:
        layers.append(layers[0].copy())
    save(path, data)
    with pytest.raises(AssetError):
        TiledMap(path)


def test_duplicate_json_keys_fail(tmp_path: Path) -> None:
    path = tmp_path / "bad.tmj"
    path.write_text('{"width":1,"width":2}')
    with pytest.raises(AssetError, match="Duplicate JSON key"):
        TiledMap(path)


def test_real_pixelorama_vertical_multirow_export() -> None:
    horizontal = PixeloramaSheet(ART / "hero.png")
    vertical = PixeloramaSheet(FIXTURES / "editors/hero_vertical.png")
    assert vertical.durations == horizontal.durations
    assert [c.to_pillow().tobytes() for c in vertical.frames] == [
        c.to_pillow().tobytes() for c in horizontal.frames
    ]
    first, second = vertical.animation(), vertical.animation()
    first.move(9)
    assert len(first._commands) == len(second._commands) + 1


@pytest.mark.parametrize("problem", ["duplicate", "outside", "incomplete", "fps", "size"])
def test_pixelorama_mismatched_metadata_fails(tmp_path: Path, problem: str) -> None:
    assets = game(tmp_path)
    data = _document(assets / "hero.json")
    if problem == "duplicate":
        data["tags"] = [{"name": "walk", "from": 1, "to": 3}] * 2
    elif problem == "outside":
        data["tags"] = [{"name": "bad", "from": 1, "to": 4}]
    elif problem == "incomplete":
        cast(dict[str, object], data["export_profile"])["number_of_frames"] = "2"
    elif problem == "fps":
        data["fps"] = 0
    else:
        data["size_x"] = 31
    save(assets / "hero.json", data)
    with pytest.raises(AssetError):
        PixeloramaSheet(assets / "hero.png")
