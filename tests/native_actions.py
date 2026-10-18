"""Exercise the first Action path on a real display; no dummy SDL backend."""

import runpy
from pathlib import Path
from unittest.mock import patch

import pygame

from plocks import Event, Sprite, Stage


def main() -> None:
    stages: list[Stage] = []

    def capture(stage: Stage) -> None:
        stages.append(stage)

    with patch.object(Stage, "run", capture):
        runpy.run_path("tests/fixtures/games/actions_proof/main.py", run_name="__main__")
    stage = stages[0]
    hero, friend = stage.objects
    assert isinstance(hero, Sprite) and isinstance(friend, Sprite)

    @stage.on_update
    def exercise(event: Event[Stage, float]) -> None:
        dt = event.data
        tick = round(stage.time / dt)
        if tick == 3:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        if tick == 15:
            assert -100 < hero.y < 0
            assert friend.x > -150
            pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        if tick == 50:
            assert hero.y == 0 and not stage._actions
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))
        if tick == 100:
            assert hero.y == -100 and not stage._actions
            target = stage._target
            assert target is not None
            Path("output/playwright").mkdir(parents=True, exist_ok=True)
            pygame.image.save(target, "output/playwright/actions-native.png")
            print("NATIVE_ACTIONS_OK", pygame.display.get_driver(), stage.time, flush=True)
            stage.stop()

    stage.run()
    assert not stage._actions and not stage.objects and stage._target is None
    print("NATIVE_ACTION_CLEANUP_OK", flush=True)


if __name__ == "__main__":
    main()
