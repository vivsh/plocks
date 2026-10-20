"""Operation-local validation and extraction of supported Tiled JSON exports."""

from __future__ import annotations

import base64
import binascii
import struct
import zlib
from collections.abc import Iterator, Mapping
from pathlib import Path, PureWindowsPath
from typing import cast
from urllib.parse import urlsplit

from PIL import Image as PillowImage

from ._asset_json import _array, _bool, _document, _float, _int, _object, _text
from .errors import AssetError
from .geometry import Bounds, Color, Point
from .imaging import Image, ImageGrid
from .tiling import TileMap


def _reference(source: Path, text: str, *, root: Path | None = None) -> Path:
    """Resolve relative export references; an optional build root enforces containment."""
    target = Path(_text(text, "asset reference"))
    if target.is_absolute() or PureWindowsPath(text).drive or urlsplit(text).scheme or "\\" in text:
        raise AssetError(f"{source}: use a relative local asset reference: {text!r}")
    current = source.parent.resolve()
    for part in target.parts:
        current = current / part
        if current.is_symlink() or current.is_junction():
            raise AssetError(f"{source}: selected symlinks/junctions are not portable: {text}")
    resolved = current.resolve()
    if root is not None and not resolved.is_relative_to(root.resolve()):
        raise AssetError(f"{source}: asset reference escapes the project: {text}")
    if not resolved.is_file():
        raise AssetError(f"{source}: missing referenced asset {text}")
    return resolved


def _solid(properties: object) -> bool | None:
    result = None
    found = False
    for raw in _array(properties, "properties"):
        item = _object(raw, "property")
        if item.get("name") == "solid":
            if found or item.get("type") != "bool":
                raise AssetError("solid must be a unique Boolean property")
            found, result = True, _bool(item.get("value"), "solid")
    return result


def _tilesets(
    path: Path, definitions: list[object], size: tuple[int, int]
) -> tuple[dict[str, Image], dict[int, bool]]:
    palette: dict[str, Image] = {}
    overrides: dict[int, bool] = {}
    for raw in definitions:
        item = _object(raw, "tileset")
        first = _int(item.get("firstgid"), "firstgid", 1)
        source = (
            path
            if "source" not in item
            else _reference(path, _text(item["source"], "tileset source"))
        )
        if source.suffix.lower() in {".tsx", ".tmx"}:
            raise AssetError(f"{source}: export the tileset as JSON (.tsj)")
        data = item if "source" not in item else _document(source)
        try:
            if (
                _int(data.get("tilewidth"), "tilewidth", 1),
                _int(data.get("tileheight"), "tileheight", 1),
            ) != size:
                raise AssetError("Tiles must match the map cell dimensions")
            offset = _object(data.get("tileoffset", {}), "tileoffset")
            if _float(offset.get("x", 0), "tile offset x") or _float(
                offset.get("y", 0), "tile offset y"
            ):
                raise AssetError("Tile offsets are not supported")
            image = _reference(
                source, _text(data.get("image"), "atlas image (image collections are unsupported)")
            )
            margin, gap = (
                _int(data.get("margin", 0), "margin"),
                _int(data.get("spacing", 0), "spacing"),
            )
            sheet = ImageGrid(image, frame_size=size, margin=(margin, margin), spacing=(gap, gap))
            count = _int(data.get("tilecount"), "tilecount", 1)
            if (
                _int(data.get("columns"), "columns", 1) != sheet.columns
                or count > sheet.rows * sheet.columns
            ):
                raise AssetError("Tileset counts do not match its atlas grid")
            if first + count > 0x10000000:
                raise AssetError("Tile IDs overlap reserved transform flags")
            for index in range(count):
                key = str(first + index)
                if key in palette:
                    raise AssetError("Overlapping tileset GID ranges")
                palette[key] = sheet.frame(row=index // sheet.columns, column=index % sheet.columns)
            defined: set[int] = set()
            for raw_tile in _array(data.get("tiles", []), "tile definitions"):
                tile = _object(raw_tile, "tile")
                index = _int(tile.get("id"), "tile id")
                if index in defined or index >= count:
                    raise AssetError("Duplicate tile definition or tile outside its atlas")
                defined.add(index)
                if any(key in tile for key in ("animation", "image", "objectgroup")):
                    raise AssetError(
                        "Animated tiles, per-tile images and tile collision shapes are unsupported; use Boolean solid"
                    )
                value = _solid(tile.get("properties", []))
                if value is not None:
                    overrides[first + index] = value
        except (AssetError, ValueError, TypeError) as error:
            raise AssetError(f"Tileset {source}: {error}") from error
    return palette, overrides


def _visual(item: dict[str, object]) -> None:
    if item.get("mode", "normal") != "normal" or _text(
        item.get("tintcolor", "#ffffffff"), "tintcolor"
    ).lower() not in {
        "#ffffffff",
        "#ffffff",
    }:
        raise AssetError("Tint and nonnormal blend modes are unsupported")


def _flatten(
    layers: list[object],
    prefix: str = "",
    offset: Point = (0, 0),
    visible: bool = True,
    opacity: float = 1,
    parallax: Point = (1, 1),
    depth: int = 0,
) -> Iterator[tuple[str, dict[str, object]]]:
    if depth >= 32:
        raise AssetError("Tiled groups may nest at most 32 levels")
    names: set[str] = set()
    for raw in layers:
        item = _object(raw, "layer").copy()
        name = _text(item.get("name"), "layer name")
        if "/" in name or name in names:
            raise AssetError(f"Duplicate layer name or '/' in name: {name!r}")
        names.add(name)
        key = prefix + name
        _visual(item)
        own_opacity = _float(item.get("opacity", 1), "opacity", 0)
        if own_opacity > 1:
            raise AssetError("Opacity must be in [0, 1]")
        x, y = (
            offset[0] + _float(item.get("offsetx", 0), "offsetx"),
            offset[1] + _float(item.get("offsety", 0), "offsety"),
        )
        px, py = (
            parallax[0] * _float(item.get("parallaxx", 1), "parallaxx", 0),
            parallax[1] * _float(item.get("parallaxy", 1), "parallaxy", 0),
        )
        alpha = opacity * own_opacity
        shown = visible and _bool(item.get("visible", True), "visible")
        if item.get("type") == "group":
            yield from _flatten(
                _array(item.get("layers"), "group layers"),
                key + "/",
                (x, y),
                shown,
                alpha,
                (px, py),
                depth + 1,
            )
        else:
            item.update(
                offsetx=x, offsety=y, visible=shown, opacity=alpha, parallaxx=px, parallaxy=py
            )
            yield key, item


def _gids(item: dict[str, object], count: int) -> tuple[int, ...]:
    data = item.get("data")
    if isinstance(data, list):
        if item.get("compression", "") or item.get("encoding", "csv") != "csv":
            raise AssetError("Array tile data must be uncompressed integer data")
        numbers = tuple(_int(n, "GID") for n in cast(list[object], data))
    elif isinstance(data, str):
        if item.get("encoding") != "base64":
            raise AssetError("Encoded tile data requires base64")
        try:
            raw = base64.b64decode(data, validate=True)
            compression = item.get("compression", "")
            if compression in {"zlib", "gzip"}:
                decoder = zlib.decompressobj(
                    zlib.MAX_WBITS if compression == "zlib" else zlib.MAX_WBITS | 16
                )
                raw = decoder.decompress(raw, count * 4 + 1)
                if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                    raise AssetError(
                        "Compressed tile data exceeds or does not match its declared size"
                    )
            elif compression:
                raise AssetError("Use uncompressed, zlib or gzip data, not zstd")
            if len(raw) != count * 4:
                raise AssetError("Tile data byte count does not match layer dimensions")
            numbers = tuple(value[0] for value in struct.iter_unpack("<I", raw))
        except (ValueError, binascii.Error, zlib.error) as error:
            raise AssetError(f"Invalid encoded tile data: {error}") from error
    else:
        raise AssetError("Tile data must be an integer array or base64 string")
    if len(numbers) != count or any(n > 0xFFFFFFFF for n in numbers):
        raise AssetError("Tile count or unsigned GID range is invalid")
    return tuple(n & ~0x10000000 for n in numbers)


def _variant(
    gid: int, base: Mapping[str, Image], variants: dict[str, Image], size: tuple[int, int]
) -> Image:
    key = str(gid)
    if key in base:
        return base[key]
    if key in variants:
        return variants[key]
    original = str(gid & 0x0FFFFFFF)
    if original not in base:
        raise AssetError(f"Unknown GID {gid} (base {original})")
    image = base[original].to_pillow()
    if gid & 0x20000000:
        if size[0] != size[1]:
            raise AssetError("Diagonal GID transforms currently require square tiles")
        image = image.transpose(PillowImage.Transpose.TRANSPOSE)
    if gid & 0x80000000:
        image = image.transpose(PillowImage.Transpose.FLIP_LEFT_RIGHT)
    if gid & 0x40000000:
        image = image.transpose(PillowImage.Transpose.FLIP_TOP_BOTTOM)
    result = Image(image)
    variants[key] = result
    return result


def _tile_layer(
    item: dict[str, object],
    base: dict[str, Image],
    overrides: dict[int, bool],
    variants: dict[str, Image],
    dimensions: tuple[int, int],
    size: tuple[int, int],
    position: Point,
    origin: Point,
    layer: int,
) -> TileMap:
    width, height = dimensions
    if (
        "chunks" in item
        or (_int(item.get("width"), "layer width", 1), _int(item.get("height"), "layer height", 1))
        != dimensions
    ):
        raise AssetError("Finite layer dimensions must match the map")
    if _float(item.get("x", 0), "layer x") or _float(item.get("y", 0), "layer y"):
        raise AssetError("Use pixel layer offsets rather than legacy tile offsets")
    gids = _gids(item, width * height)
    palette = base.copy()
    for gid in set(gids) - {0}:
        palette[str(gid)] = _variant(gid, base, variants, size)
    default = _solid(item.get("properties", [])) or False
    solid = {key for key in palette if overrides.get(int(key) & 0x0FFFFFFF, default)}
    rows = [
        [None if gid == 0 else str(gid) for gid in gids[start : start + width]]
        for start in range(0, len(gids), width)
    ]
    return TileMap(
        rows,
        palette,
        tile_size=size,
        solid=solid,
        x=position[0],
        y=position[1],
        layer=layer,
        visible=_bool(item["visible"], "visible"),
        opacity=_float(item["opacity"], "opacity"),
        parallax=(_float(item["parallaxx"], "parallaxx"), _float(item["parallaxy"], "parallaxy")),
        parallax_origin=origin,
    )


def _markers(
    group: str,
    item: dict[str, object],
    position: Point,
    points: dict[str, Point],
    regions: dict[str, Bounds],
) -> None:
    for raw in _array(item.get("objects"), "objects"):
        obj = _object(raw, "object")
        name = _text(obj.get("name"), "object name")
        if "/" in name:
            raise AssetError("Object names cannot contain '/'")
        key = group + "/" + name
        if any(
            field in obj
            for field in ("gid", "template", "ellipse", "polygon", "polyline", "text", "capsule")
        ) or _float(obj.get("rotation", 0), "rotation"):
            raise AssetError(f"{key}: use a point or unrotated rectangle marker")
        x, y = position[0] + _float(obj.get("x"), "x"), position[1] - _float(obj.get("y"), "y")
        if _bool(obj.get("point", False), "point"):
            if key in points:
                raise AssetError(f"Duplicate point {key}")
            points[key] = (x, y)
        else:
            if key in regions:
                raise AssetError(f"Duplicate region {key}")
            width, height = (
                _float(obj.get("width"), "width", 0),
                _float(obj.get("height"), "height", 0),
            )
            regions[key] = Bounds(x, y - height, x + width, y)


def _color(value: object) -> Color:
    text = _text(value, "background color")
    if not text.startswith("#") or len(text) not in (7, 9):
        raise AssetError("Tiled colors must be #RRGGBB or #AARRGGBB")
    try:
        channels = tuple(int(text[i : i + 2], 16) for i in range(1, len(text), 2))
    except ValueError as error:
        raise AssetError("Invalid Tiled color") from error
    return (
        (channels[1], channels[2], channels[3], channels[0])
        if len(channels) == 4
        else (channels[0], channels[1], channels[2])
    )
