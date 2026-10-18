"""Run a desktop game from its project folder."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from importlib.resources import as_file
from pathlib import Path
from typing import cast

from ._examples import _copy, _example, _names


def _linked(path: Path) -> bool:
    """Treat symlinks and Windows junctions equally at the launch boundary."""
    return path.is_symlink() or path.is_junction()


def _entry(root: Path) -> Path:
    """Validate the optional custom entry without running the game or changing cwd."""
    filename = root / "plocks.toml"
    entry: object = "main.py"
    if filename.exists() or filename.is_symlink():
        if _linked(filename):
            raise ValueError("plocks.toml must not be a symlink or junction")
        with filename.open("rb") as stream:
            game: object = tomllib.load(stream).get("game", {})
        if not isinstance(game, dict):
            raise ValueError("plocks.toml requires a [game] table")
        settings = cast(dict[str, object], game)
        unknown = settings.keys() - {"entry"}
        if unknown:
            raise ValueError(f"Unknown game setting(s): {', '.join(sorted(unknown))}")
        entry = settings.get("entry", "main.py")
    if not isinstance(entry, str) or not entry.strip():
        raise ValueError("game.entry must be a nonempty Python file path")
    path = Path(entry)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".py":
        raise ValueError("game.entry must be a project-relative Python file without '..'")
    current = root
    for part in path.parts:
        current = current / part
        if _linked(current):
            raise ValueError(f"Selected symlinks/junctions are not supported: {path}")
    if not current.is_file():
        raise ValueError(f"Entry script does not exist: {path}")
    return path


def _run(project: Path) -> int:
    """Launch one validated project with its own working directory and module path."""
    if _linked(project):
        raise ValueError("The selected project must not be a symlink or junction")
    root = project.resolve()
    if not root.is_dir():
        raise ValueError(f"Not a project directory: {root}")
    entry = _entry(root)
    code = (
        f"import sys,runpy; sys.path.insert(0,{str(entry.parent)!r}); "
        f"runpy.run_path({str(entry)!r},run_name='__main__')"
    )
    return subprocess.call([sys.executable, "-c", code], cwd=root)


def main() -> int:
    """Run local/bundled games, list examples, or copy one into a new editable folder."""
    parser = argparse.ArgumentParser(prog="plocks", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run a local project or bundled example")
    run.add_argument("project", nargs="?", default=".", type=Path)
    examples = commands.add_parser("examples", help="List or copy bundled examples")
    examples.add_argument("name", nargs="?")
    examples.add_argument("--copy-to", type=Path, metavar="FOLDER")
    args = parser.parse_args()
    try:
        if args.command == "examples":
            if (args.name is None) != (args.copy_to is None):
                parser.error("Use 'plocks examples NAME --copy-to FOLDER' to copy an example")
            if args.name is None:
                print("\n".join(_names()))
            else:
                print(f"Copied to {_copy(args.name, args.copy_to)}")
            return 0
        project = args.project
        if project.exists() or _linked(project):
            return _run(project)
        parts = project.parts
        if len(parts) == 1:
            name = parts[0]
        elif len(parts) == 2 and parts[0] == "examples":
            name = parts[1]
        else:
            return _run(project)
        with as_file(_example(name)) as root:
            return _run(root)
    except KeyboardInterrupt:
        return 130
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"plocks: {error}", file=sys.stderr)
        return 1
