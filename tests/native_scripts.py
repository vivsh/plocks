"""Prove shared Scripts, runtime branches, Events and detach on a native display."""

import runpy
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

import pygame

from plocks import Event, Sprite, Stage


def main() -> None:
    stages: list[Stage] = []
    game_root = Path(__file__).resolve().parent / "fixtures/games/scripts_proof"
    with chdir(game_root), patch.object(Stage, "run", lambda stage: stages.append(stage)):
        game = runpy.run_path("main.py", run_name="__main__")
    stage = stages[0]
    first, second = stage.objects
    assert isinstance(first, Sprite) and isinstance(second, Sprite)
    frozen: list[tuple[float, float]] = []

    @stage.on_update
    def exercise(event: Event[Stage, float]) -> None:
        tick = round(stage.time / event.data)
        if tick == 3:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        if tick == 15:
            assert -120 < first.x < -60 and 40 < second.x < 100
        if tick == 40:
            assert first.x == -60 and second.x == 100
            assert len(game["arrivals"]) == 2 and not stage._actions
            pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        if tick == 50:
            assert first.y > -40 and second.y > 40
            first.stop()
            stage.remove(second)
            frozen.extend((first.position, second.position))
        if tick == 80:
            assert [first.position, second.position] == frozen and not stage._actions
            print("SHARED_SCRIPT_NATIVE_OK", pygame.display.get_driver(), flush=True)
            stage.stop()

    stage.run()
    assert not stage.objects and not stage._messages and not stage._message_handlers
    assert not stage._actions and stage._target is None
    print("SHARED_SCRIPT_CLEANUP_OK", flush=True)


if __name__ == "__main__":
    main()
