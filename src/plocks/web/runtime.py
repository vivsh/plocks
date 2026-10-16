"""Pinned browser artifacts, verified before use; no persistent download cache."""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
import zipfile
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import cast

from ..errors import BuildError

type _Artifact = tuple[str, str, int, str]
"""Manifest (relative path, URL, byte count, SHA-256); an ordinary immutable tuple."""


def artifacts(*, physics: bool = False) -> tuple[_Artifact, ...]:
    """Read the shipped immutable runtime inventory, including expected hashes."""
    names = ("runtime-lock.json", "physics-lock.json") if physics else ("runtime-lock.json",)
    return tuple(artifact for name in names for artifact in _inventory(name))


def _inventory(name: str) -> tuple[_Artifact, ...]:
    """Validate either packaged dependency inventory through the same boundary."""
    document: object = json.loads(files(__package__).joinpath(name).read_text())
    if not isinstance(document, list):
        raise BuildError("Invalid packaged runtime inventory")
    result: list[_Artifact] = []
    for item in cast(list[object], document):
        record = cast(dict[str, object], item)
        if (
            not isinstance(item, dict)
            or not isinstance(record.get("path"), str)
            or not isinstance(record.get("url"), str)
            or not isinstance(record.get("size"), int)
            or not isinstance(record.get("sha256"), str)
        ):
            raise BuildError("Invalid packaged runtime artifact")
        result.append(
            (
                cast(str, record["path"]),
                cast(str, record["url"]),
                cast(int, record["size"]),
                cast(str, record["sha256"]),
            )
        )
    return tuple(result)


def download(artifact: _Artifact, destination: Path) -> Path:
    """Read a shipped notice or fetch a runtime artifact, validating its exact digest."""
    path, url, size, digest = artifact
    try:
        if path.startswith("notices/"):
            body = files(__package__).joinpath(path).read_bytes()
        else:
            request = urllib.request.Request(url, headers={"User-Agent": "plocks/0.3"})
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read(size + 1)
    except (OSError, urllib.error.URLError) as error:
        raise BuildError(f"Cannot obtain {url}: {error}") from error
    if len(body) != size or hashlib.sha256(body).hexdigest() != digest:
        raise BuildError(f"Runtime artifact changed or is damaged: {url}")
    target = destination / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    return target


def extract_wheel(wheel: Path, destination: Path) -> None:
    """Stage only core package files and notices, never run wheel-provided code."""
    with zipfile.ZipFile(wheel) as archive:
        for item in archive.infolist():
            path = PurePosixPath(item.filename)
            if path.is_absolute() or ".." in path.parts:
                raise BuildError(f"Unsafe wheel path: {path}")
            if item.is_dir() or any(
                part in {"tests", "examples", "__pycache__"} for part in path.parts
            ):
                continue
            if path.suffix in {".pyc", ".pyi"}:
                continue
            if not (
                path.parts[0]
                in {
                    "pygame",
                    "PIL",
                    "typing_extensions.py",
                    "pymunk",
                    "cffi",
                    "pycparser",
                    "_cffi_backend.cpython-312-wasm32-emscripten.so",
                }
                or ".dist-info" in path.parts[0]
            ):
                continue
            target = destination.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(item))
