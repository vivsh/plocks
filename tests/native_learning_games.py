"""Open each learning game briefly on a real display and capture its scene."""

import runpy
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pygame

from plocks import Event, Stage


def exercise_game(root: Path, output: Path, name: str) -> None:
    """Run one isolated native window and its own module variables."""
    stages: list[Stage] = []

    def capture(stage: Stage) -> None:
        stages.append(stage)

    with patch.object(Stage, "run", capture):
        runpy.run_path(str(root / "examples" / name / "main.py"), run_name="__main__")
    stage = stages[0]

    @stage.on_update
    def exercise(event: Event[Stage, float]) -> None:
        dt = event.data
        tick = round(stage.time / dt)
        if tick == 3:
            for key in (pygame.K_RIGHT, pygame.K_SPACE):
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
        if tick == 38:
            target = stage._target
            assert target is not None
            pygame.image.save(target, str(output / f"learning-{name}-native.png"))
            print(name, pygame.display.get_driver(), len(stage.objects), flush=True)
            stage.stop()

    stage.run()
    assert not stage.objects and not stage._actions and stage._target is None


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "output/playwright"
    output.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 1:
        exercise_game(root, output, sys.argv[1])
        return
    for name in (
        "jungle_run",
        "mario",
        "platformer",
        "fruit_ninja",
        "geometry_dash",
        "snake_run",
        "temple_run",
        "scrolling_world",
        "dojo_duel",
        "sunset_sprint",
    ):
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), name], check=True, timeout=15
        )
    print("NATIVE_LEARNING_GAMES_OK", flush=True)


if __name__ == "__main__":
    main()
