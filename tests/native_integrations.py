"""Native first-path proof using real editor exports and mapped keyboard input."""

import runpy
from pathlib import Path
from unittest.mock import patch

import pygame

from plocks import Event, Stage


def main() -> None:
    stages: list[Stage] = []
    with patch.object(Stage, "run", lambda stage: stages.append(stage)):
        game = runpy.run_path(
            str(Path(__file__).parent / "fixtures/games/integrations_proof/main.py"),
            run_name="__main__",
        )
        game = game["draw"].__globals__
    stage = stages[0]
    hero, friend = game["hero"], game["friend"]
    frames: set[int] = set()
    initial = hero.y

    @stage.on_update
    def exercise(event: Event[Stage, float]) -> None:
        tick = round(stage.time * stage.tick_rate)
        frames.add(game["art"].frames.index(hero.costume))
        if tick == 3:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        if tick == 10:
            assert hero.y > initial + 20 and friend.x > -150
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        if tick == 35:
            assert abs(hero.y - initial) < 1e-9 and game["presses"] == 1
            assert frames == {0, 1, 2}
            print("INTEGRATIONS_NATIVE_OK", pygame.display.get_driver(), flush=True)
            stage.stop()

    stage.run()
    assert stage._target is None and not stage.objects and not stage._actions
    assert not any(p.connected for p in stage.gamepads)
    print("INTEGRATIONS_NATIVE_CLEANUP_OK", flush=True)


if __name__ == "__main__":
    main()
