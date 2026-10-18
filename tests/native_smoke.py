"""Run the combined example on a real display and audio device, then close cleanly.

Run from the repository root with the dummy SDL variables unset. Input is posted
through pygame's event queue; human confirmation of audibility remains separate.
"""

import os
import runpy
from pathlib import Path
from unittest.mock import patch

import pygame

from plocks import Event, Stage


def main() -> None:
    """Exercise the unchanged example through its native execution path."""
    root = Path(__file__).resolve().parents[1]
    screenshot = root / "output/playwright/world-native.png"
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    stages: list[Stage] = []
    original = Path.cwd()

    def capture(stage: Stage) -> None:
        stages.append(stage)

    try:
        os.chdir(root / "tests/fixtures/games/animated_world")
        with patch.object(Stage, "run", capture):
            runpy.run_path("main.py", run_name="__main__")
        stage = stages[0]

        @stage.on_update
        def exercise(event: Event[Stage, float]) -> None:
            dt = event.data
            tick = round(stage.time / dt)
            if tick == 6:
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
            if tick == 12:
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
            if tick == 13:
                assert stage._voices and not stage._voices[0].finished
                print("NATIVE_AUDIO", pygame.mixer.get_init(), flush=True)
            if tick == 30:
                pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_RIGHT))
                pygame.event.post(
                    pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(400, 285), button=1)
                )
            if tick == 50:
                assert stage._target is not None
                pygame.image.save(stage._target, screenshot)
                print("NATIVE_DISPLAY", pygame.display.get_driver(), stage.time, flush=True)
                stage.stop()

        stage.run()
        assert stage._state == "closed" and stage._target is None and not stage._voices
        print("NATIVE_CLEANUP_OK", flush=True)
    finally:
        os.chdir(original)


if __name__ == "__main__":
    main()
