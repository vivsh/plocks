"""Exercise the teaching demo on the actual desktop driver, then stop it."""

import runpy
from pathlib import Path
from unittest.mock import patch

import pygame

from plocks import Stage
from plocks._operations import _BubbleRun


def main() -> None:
    """Post real SDL input and verify dialogue/motion before native teardown."""
    stages: list[Stage] = []

    def capture(stage: Stage) -> None:
        stages.append(stage)

    with patch.object(Stage, "run", capture):
        runpy.run_path("examples/bubbles/main.py", run_name="__main__")
    stage = stages[0]
    hero, friend = stage.objects[:2]

    @stage.on_update
    def exercise(dt: float) -> None:
        tick = round(stage.time / dt)
        if tick == 2:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        if tick == 10:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_t))
        if tick == 25:
            from plocks import Sprite

            assert isinstance(hero, Sprite) and isinstance(friend, Sprite)
            assert isinstance(hero._bubble, _BubbleRun) and hero.x > -100 and friend.x > -160
            assert stage._target is not None
            path = Path("output/playwright/bubbles-native.png")
            path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(stage._target, path)
            print("BUBBLE_NATIVE", pygame.display.get_driver(), stage.time, hero.x, friend.x)
        if tick == 145:
            from plocks import Sprite

            assert isinstance(hero, Sprite)
            assert hero._bubble is None and hero.x == 0 and not stage._runs
            stage.stop()

    stage.run()
    assert stage._target is None and not stage.objects and not stage._runs
    print("BUBBLE_NATIVE_CLEANUP_OK")


if __name__ == "__main__":
    main()
