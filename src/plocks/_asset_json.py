"""Small validation boundaries for exported asset documents; no retained parser state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from .errors import AssetError
from .geometry import _integer, _number


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise AssetError(f"Duplicate JSON key {key!r}")
        result[key] = value
    return result


def _document(path: Path) -> dict[str, object]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
        return _object(value, str(path))
    except (OSError, UnicodeError, ValueError, TypeError, AssetError) as error:
        raise AssetError(f"Cannot read exported asset {path}: {error}") from error


def _object(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in cast(dict[object, object], value)
    ):
        raise AssetError(f"{name} must be a JSON object")
    return cast(dict[str, object], value)


def _array(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise AssetError(f"{name} must be a JSON array")
    return cast(list[object], value)


def _int(value: object, name: str, minimum: int = 0) -> int:
    try:
        return _integer(cast(int, value), name, minimum=minimum)
    except (ValueError, TypeError) as error:
        raise AssetError(str(error)) from error


def _float(value: object, name: str, minimum: float | None = None) -> float:
    try:
        return _number(cast(float, value), name, minimum=minimum)
    except (ValueError, TypeError) as error:
        raise AssetError(str(error)) from error


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AssetError(f"{name} must be a nonempty string")
    return value


def _bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise AssetError(f"{name} must be a boolean")
    return value
