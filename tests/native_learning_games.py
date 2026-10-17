"""Open each learning game briefly on a real display and capture its scene."""

import runpy
from pathlib import Path
from unittest.mock import patch

import pygame

from plocks import Stage


def exercise_game(root: Path, output: Path, name: str) -> None:
    """Run one isolated native window and its own module variables."""
    stages: list[Stage] = []

    def capture(stage: Stage) -> None:
        stages.append(stage)

    with patch.object(Stage, "run", capture):
        runpy.run_path(str(root / "examples" / name / "main.py"), run_name="__main__")
    stage = stages[0]

    @stage.on_update
    def exercise(dt: float) -> None:
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
    for name in (
        "jungle_run",
        "mario",
        "platformer",
        "fruit_ninja",
        "geometry_dash",
        "snake_run",
        "temple_run",
        "scrolling_world",
    ):
        exercise_game(root, output, name)
    print("NATIVE_LEARNING_GAMES_OK", flush=True)


if __name__ == "__main__":
    main()
