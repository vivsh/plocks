"""Operation-local file selection and conservative static portability checks."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from ..errors import BuildError
from .project import ProjectConfig, _is_link

_EXCLUDED = frozenset({"dist", "build", "venv", "env", "__pycache__", "node_modules", "output"})
_AUDIO = frozenset(
    {
        ".wav",
        ".mp3",
        ".aiff",
        ".aif",
        ".aifc",
        ".flac",
        ".m4a",
        ".opus",
        ".aac",
        ".mid",
        ".midi",
        ".wma",
        ".oga",
        ".au",
        ".snd",
        ".caf",
    }
)
_UNSUPPORTED = frozenset(
    {"tkinter", "threading", "multiprocessing", "subprocess", "socket", "ctypes"}
)


def _skip(path: Path) -> bool:
    return any(part.startswith(".") or part in _EXCLUDED for part in path.parts)


def _walk(root: Path, selected: Path, *, python_only: bool = False) -> list[Path]:
    """Traverse selected trees without following any symlink or development tree."""
    result: list[Path] = []
    pending = [selected]
    while pending:
        relative = pending.pop()
        if _skip(relative):
            continue
        absolute = root / relative
        if _is_link(absolute):
            if python_only and relative.suffix != ".py" and not absolute.is_dir():
                continue
            raise BuildError(f"Selected symlinks/junctions are not portable: {relative}")
        if absolute.is_dir():
            pending.extend(child.relative_to(root) for child in sorted(absolute.iterdir()))
        elif (
            absolute.is_file()
            and absolute.suffix not in {".pyc", ".pyo"}
            and (not python_only or absolute.suffix == ".py")
        ):
            result.append(relative)
    return result


def collect(config: ProjectConfig) -> tuple[Path, ...]:
    """Select source/assets and reject path collisions and nonportable audio."""
    paths = set(_walk(config.root, Path(), python_only=True))
    for selected in (*config.asset_paths, *config.include_paths):
        paths.update(_walk(config.root, selected))
    if config.entry not in paths:
        raise BuildError("The entry is excluded by the project file-selection rules")
    folded: dict[str, Path] = {}
    for path in sorted(paths):
        for length in range(1, len(path.parts) + 1):
            prefix = Path(*path.parts[:length])
            key = prefix.as_posix().casefold()
            if key in folded and folded[key] != prefix:
                raise BuildError(f"Case-insensitive path collision: {folded[key]} and {prefix}")
            folded[key] = prefix
        if path.suffix.lower() in _AUDIO:
            raise BuildError(f"Use OGG/Vorbis audio for browser builds: {path}")
        if path.suffix.lower() == ".ogg":
            with (config.root / path).open("rb") as stream:
                header = stream.read(4096)
            if not header.startswith(b"OggS") or b"\x01vorbis" not in header:
                raise BuildError(f"Use OGG/Vorbis, rather than another OGG codec: {path}")
    return tuple(sorted(paths))


def check_source(config: ProjectConfig, paths: tuple[Path, ...]) -> None:
    """Check literal imports/asset names, without claiming to prove computed paths."""
    local = {path.parts[0].removesuffix(".py") for path in paths if path.suffix == ".py"}
    local.update(path.stem for path in paths if path.suffix == ".py")
    supported = sys.stdlib_module_names | {"plocks", "pygame", "PIL"} | local
    for path in paths:
        if path.suffix != ".py":
            continue
        try:
            tree = ast.parse(
                (config.root / path).read_text(encoding="utf-8"),
                filename=str(path),
                feature_version=(3, 12),
            )
        except (OSError, SyntaxError, UnicodeError) as error:
            raise BuildError(f"Cannot parse {path}: {error}") from error
        asset_names: set[str] = set()
        module_names: set[str] = set()
        for imported in tree.body:
            if isinstance(imported, ast.ImportFrom) and imported.module == "plocks":
                asset_names.update(
                    alias.asname or alias.name
                    for alias in imported.names
                    if alias.name in {"Sprite", "Costume", "SpriteSheet", "Sound"}
                )
            if isinstance(imported, ast.Import):
                module_names.update(
                    alias.asname or alias.name for alias in imported.names if alias.name == "plocks"
                )
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                if name not in supported or name in _UNSUPPORTED:
                    raise BuildError(
                        f"{path}:{getattr(node, 'lineno', 1)}: unsupported browser import {name!r}; vendor pure Python modules locally"
                    )
            if isinstance(node, ast.Call):
                _check_asset(paths, path, node, asset_names, module_names)


def _check_asset(
    paths: tuple[Path, ...],
    path: Path,
    node: ast.Call,
    asset_names: set[str],
    module_names: set[str],
) -> None:
    function = node.func
    identified = isinstance(function, ast.Name) and function.id in asset_names
    if (
        isinstance(function, ast.Attribute)
        and isinstance(function.value, ast.Name)
        and function.value.id in module_names
    ):
        identified = function.attr in {"Sprite", "Costume", "SpriteSheet", "Sound"}
    if not identified or not node.args:
        return
    argument = node.args[0]
    if not isinstance(argument, ast.Constant) or not isinstance(argument.value, str):
        return
    asset = Path(argument.value)
    if asset.is_absolute() or ".." in asset.parts or asset not in paths:
        raise BuildError(
            f"{path}:{node.lineno}: asset {str(asset)!r} is missing from the bundle; place it under assets/ or game.include"
        )
