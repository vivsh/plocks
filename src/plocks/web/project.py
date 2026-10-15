"""Validated per-command project configuration; no game code is evaluated."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from ..errors import BuildError


@dataclass(frozen=True)
class ProjectConfig:
    """One validated project root and its explicitly selected distribution inputs."""

    root: Path
    entry: Path
    title: str
    asset_paths: tuple[Path, ...]
    include_paths: tuple[Path, ...]
    runtime_mode: Literal["cdn", "self-contained"]


def _is_link(path: Path) -> bool:
    """Reject both symbolic links and Windows directory junctions at build boundaries."""
    return path.is_symlink() or path.is_junction()


def _relative(root: Path, text: str) -> Path:
    path = Path(text)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise BuildError(f"Use a project-relative path without '..': {text}")
    current = root
    for part in path.parts:
        current = current / part
        if _is_link(current):
            raise BuildError(f"Selected symlinks/junctions are not portable: {text}")
    if not current.exists():
        raise BuildError(f"Project path does not exist: {text}")
    return path


def _paths(root: Path, value: object, name: str) -> tuple[Path, ...]:
    if not isinstance(value, list):
        raise BuildError(f"game.{name} must be a list of project-relative paths")
    items = cast(list[object], value)
    if not all(isinstance(item, str) for item in items):
        raise BuildError(f"game.{name} must contain only paths")
    return tuple(_relative(root, cast(str, item)) for item in items)


def load_project(path: str | Path, *, self_contained: bool = False) -> ProjectConfig:
    """Read optional plocks.toml and validate all selected roots before building."""
    if _is_link(Path(path)):
        raise BuildError("The selected project directory must not be a symlink or junction")
    root = Path(path).resolve()
    if not root.is_dir():
        raise BuildError(f"Not a project directory: {root}")
    filename = root / "plocks.toml"
    settings: dict[str, object] = {}
    try:
        if filename.exists():
            if _is_link(filename):
                raise BuildError("plocks.toml must not be a symlink or junction")
            with filename.open("rb") as stream:
                document = tomllib.load(stream)
            game = document.get("game", {})
            if not isinstance(game, dict):
                raise BuildError("plocks.toml requires a [game] table")
            settings = cast(dict[str, object], game)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise BuildError(f"Cannot read {filename}: {error}") from error
    unknown = settings.keys() - {"entry", "title", "assets", "include"}
    if unknown:
        raise BuildError(f"Unknown game setting(s): {', '.join(sorted(unknown))}")
    entry = settings.get("entry", "main.py")
    title = settings.get("title", root.name)
    if not isinstance(entry, str) or not isinstance(title, str) or not title.strip():
        raise BuildError("game.entry and game.title must be nonempty strings")
    entry_path = _relative(root, entry)
    if entry_path.suffix != ".py" or not (root / entry_path).is_file():
        raise BuildError("game.entry must name a Python file")
    assets = settings.get("assets", ["assets"] if (root / "assets").exists() else [])
    return ProjectConfig(
        root,
        entry_path,
        title,
        _paths(root, assets, "assets"),
        _paths(root, settings.get("include", []), "include"),
        "self-contained" if self_contained else "cdn",
    )
