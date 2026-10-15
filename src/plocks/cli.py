"""Build, preview, or run a game; no hosting credentials or deployment required."""

from __future__ import annotations

import argparse
import functools
import http.server
import subprocess
import sys
from pathlib import Path

from .errors import BuildError
from .web.build import build
from .web.project import load_project


def main() -> int:
    """Run the command-line interface, returning a nonzero status on failure."""
    parser = argparse.ArgumentParser(prog="plocks", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "serve", "build"):
        command = commands.add_parser(name)
        command.add_argument("project", nargs="?", default=".", type=Path)
        if name != "run":
            command.add_argument("--self-contained", action="store_true")
        if name == "serve":
            command.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    try:
        if args.command == "run":
            config = load_project(args.project)
            entry = repr(str(config.entry))
            code = f"import sys,runpy; sys.path.insert(0,{str(config.entry.parent)!r}); runpy.run_path({entry},run_name='__main__')"
            return subprocess.call([sys.executable, "-c", code], cwd=config.root)
        website = build(args.project, self_contained=args.self_contained)
        print(f"Website: {website}\nArchive: {website.parent / 'game-web.zip'}", flush=True)
        if args.command == "serve":
            handler = functools.partial(
                http.server.SimpleHTTPRequestHandler, directory=str(website)
            )
            with http.server.HTTPServer(("127.0.0.1", args.port), handler) as server:
                print(f"Open http://127.0.0.1:{server.server_port}/", flush=True)
                server.serve_forever()
        return 0
    except KeyboardInterrupt:
        return 130
    except (BuildError, OSError, subprocess.SubprocessError) as error:
        print(f"plocks: {error}", file=sys.stderr)
        return 1
