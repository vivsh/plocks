"""Run wheel-installed examples outside the checkout in distribution CI."""

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> None:
    """Exercise the installed CLI, real game loops, editable copies and shutdown."""
    with TemporaryDirectory(prefix="plocks-installed-") as directory:
        root = Path(directory)
        # A validation-only hook closes real game windows after a few frames.
        # It is on the child path without exposing any checkout source modules.
        (root / "sitecustomize.py").write_text(
            "from pathlib import Path\n"
            "import plocks\n"
            "from plocks import Stage\n"
            "assert Path(plocks.__file__).parent.parent.name == 'site-packages'\n"
            "original = Stage.run\n"
            "def exercise(stage):\n"
            "    frames = 0\n"
            "    @stage.on_draw\n"
            "    def inspect(event):\n"
            "        nonlocal frames\n"
            "        frames += 1\n"
            "        if frames == 8:\n"
            "            assert stage.running and stage.objects and stage.time > 0\n"
            "            stage.stop()\n"
            "    original(stage)\n"
            "    assert not stage.objects and not stage._actions and not stage._voices\n"
            "    assert stage._target is None\n"
            "    print('INSTALLED_GAME_OK', flush=True)\n"
            "Stage.run = exercise\n"
        )
        environment = {
            **os.environ,
            "PYTHONPATH": str(root),
            "SDL_VIDEODRIVER": "dummy",
            "SDL_AUDIODRIVER": "dummy",
            "PYGAME_HIDE_SUPPORT_PROMPT": "1",
        }
        invoke = "from plocks.cli import main; raise SystemExit(main())"

        def command(*arguments: str) -> str:
            """Use the console entry function with an installed interpreter and isolated cwd."""
            result = subprocess.run(
                [sys.executable, "-c", invoke, *arguments],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            assert result.returncode == 0, (arguments, result.stdout, result.stderr)
            return result.stdout

        names = command("examples").splitlines()
        assert len(names) == 10
        assert "dojo_duel" not in names and "sunset_sprint" not in names
        for index, name in enumerate(names):
            spelling = name if index % 2 else f"examples/{name}"
            assert "INSTALLED_GAME_OK" in command("run", spelling)
        command("examples", "platformer", "--copy-to", "my-game")
        assert (root / "my-game/assets/hero.png").is_file()
        entry = root / "my-game/main.py"
        entry.write_text(entry.read_text() + "\nprint('EDITED_GAME_OK')\n")
        assert "EDITED_GAME_OK" in command("run", "my-game")
        print(f"INSTALLED_EXAMPLES_OK: {len(names)} games and an editable copy")


if __name__ == "__main__":
    main()
