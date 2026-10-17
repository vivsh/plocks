"""Exercise the physics proof with the actual macOS display and shared runtime loop."""

import runpy
from unittest.mock import patch

import pygame

from plocks import Sprite, Stage


def main() -> None:
    stages: list[Stage] = []

    def capture(stage: Stage) -> None:
        stages.append(stage)

    with patch.object(Stage, "run", capture):
        runpy.run_path("tests/fixtures/games/physics_proof/main.py", run_name="__main__")
    stage = stages[0]
    hero, friend = stage.objects[1:]
    assert isinstance(hero, Sprite) and isinstance(friend, Sprite)

    @stage.on_update
    def exercise(dt: float) -> None:
        tick = round(stage.time / dt)
        if tick == 75:
            assert hero.body.grounded and friend.x > -100
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        if tick == 90:
            assert hero.y > -60 and hero._bubble is not None
            assert stage._target is not None
            pygame.image.save(stage._target, "output/playwright/physics-native.png")
            print(
                "NATIVE_PHYSICS_OK",
                pygame.display.get_driver(),
                hero.position,
                friend.position,
                flush=True,
            )
            stage.stop()

    stage.run()
    assert stage.physics._space is None and not stage._actions and not stage.objects
    print("NATIVE_PHYSICS_CLEANUP_OK", flush=True)


if __name__ == "__main__":
    main()
