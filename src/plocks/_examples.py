"""Discover and copy installed example resources without retained state."""

from __future__ import annotations

import shutil
from importlib.resources import as_file, files
from importlib.resources.abc import Traversable
from pathlib import Path


def _names() -> tuple[str, ...]:
    """Derive the example catalog from directories containing a main.py."""
    return tuple(
        sorted(
            item.name
            for item in files("plocks").joinpath("_games").iterdir()
            if item.is_dir() and item.joinpath("main.py").is_file()
        )
    )


def _example(name: str) -> Traversable:
    """Select an installed example by its exact catalog name, excluding escaping paths."""
    if name not in _names():
        raise ValueError(f"Unknown example {name!r}. Available: {', '.join(_names())}")
    return files("plocks").joinpath("_games").joinpath(name)


def _copy(name: str, destination: Path) -> Path:
    """Copy into a new folder; preserve existing work and clean up an interrupted copy."""
    target = destination.absolute()
    with as_file(_example(name)) as source:
        target.mkdir(parents=True, exist_ok=False)
        try:
            shutil.copytree(
                source,
                target,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "dist", ".*"),
            )
        except BaseException as error:
            try:
                shutil.rmtree(target)
            except OSError as cleanup:
                error.add_note(f"Could not remove the partial example at {target}: {cleanup}")
            raise
    return target
