"""Local parsing and validation for the supported single-image JSON Hash profile."""

from __future__ import annotations

from collections.abc import Mapping
from inspect import iscoroutine
from pathlib import Path

from ._asset_json import _bool, _document, _float, _int, _object, _text
from .errors import AssetError
from .imaging import Anchor, Image


def _snapshot(values: Mapping[str, Image]) -> dict[str, Image]:
    if not isinstance(values, Mapping):
        if iscoroutine(values):
            values.close()
        raise TypeError("A synchronous ImageMap loader must return Mapping[str, Image]")
    result: dict[str, Image] = {}
    for name, image in values.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("ImageMap names must be nonempty strings")
        if not isinstance(image, Image):
            raise TypeError(f"ImageMap value for {name!r} must be Image")
        if name in result:
            raise ValueError(f"Duplicate ImageMap name {name!r}")
        result[name] = image
    if not result:
        raise ValueError("An ImageMap requires at least one image")
    return result


def _packing(meta: dict[str, object], atlas: Image) -> None:
    if "size" in meta:
        size = _object(meta["size"], "meta.size")
        if (_int(size.get("w"), "atlas width", 1), _int(size.get("h"), "atlas height", 1)) != (
            atlas.width,
            atlas.height,
        ):
            raise AssetError("JSON meta.size does not match the atlas image")
    if "scale" in meta:
        scale = meta["scale"]
        if isinstance(scale, str):
            try:
                scale = float(scale)
            except ValueError as error:
                raise AssetError("meta.scale must be 1") from error
        if _float(scale, "meta.scale") != 1:
            raise AssetError("Export ImageMap at 100% scale, or use a custom metadata callable")
    if meta.get("related_multi_packs"):
        raise AssetError(
            "ImageMap supports one atlas; export a single image or use a custom loader"
        )


def _rectangle(entry: dict[str, object], name: str, atlas: Image) -> tuple[int, int, int, int]:
    for flag in ("rotated", "trimmed"):
        if _bool(entry.get(flag, False), f"{name}.{flag}"):
            raise AssetError(
                f"{name!r} is {flag}; export unrotated/untrimmed images or use a custom metadata callable"
            )
    rect = _object(entry.get("frame"), f"{name}.frame")
    x, y = _int(rect.get("x"), "frame.x"), _int(rect.get("y"), "frame.y")
    w, h = _int(rect.get("w"), "frame.w", 1), _int(rect.get("h"), "frame.h", 1)
    if x + w > atlas.width or y + h > atlas.height:
        raise AssetError(f"ImageMap frame {name!r} lies outside the atlas")
    if "sourceSize" in entry:
        size = _object(entry["sourceSize"], f"{name}.sourceSize")
        if (_int(size.get("w"), "source width", 1), _int(size.get("h"), "source height", 1)) != (
            w,
            h,
        ):
            raise AssetError(f"{name!r}: untrimmed sourceSize must match frame dimensions")
    if "spriteSourceSize" in entry:
        size = _object(entry["spriteSourceSize"], f"{name}.spriteSourceSize")
        values = tuple(
            _int(size.get(key), f"spriteSourceSize.{key}") for key in ("x", "y", "w", "h")
        )
        if values != (0, 0, w, h):
            raise AssetError(f"{name!r}: export untrimmed frames or use a custom metadata callable")
    return x, y, w, h


def _read(atlas: Image, path: Path) -> dict[str, Image]:
    """Normalize decoded crops, discarding the atlas/JSON once construction finishes."""
    try:
        data = _document(path)
        _packing(_object(data.get("meta", {}), "meta"), atlas)
        frames = _object(data.get("frames"), "frames (JSON Hash)")
        if not frames:
            raise AssetError("ImageMap requires at least one named frame")
        result: dict[str, Image] = {}
        # One operation-local Pillow snapshot, rather than a full atlas copy per crop.
        pixels = atlas.to_pillow()
        for name, value in frames.items():
            _text(name, "image name")
            rect = _rectangle(_object(value, name), name, atlas)
            x, y, w, h = rect
            result[name] = Image(pixels.crop((x, y, x + w, y + h)), anchor=Anchor.CENTER)
        return result
    except AssetError as error:
        raise AssetError(f"Cannot load ImageMap metadata {path}: {error}") from error
