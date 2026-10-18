"""Prove independent state, shared score, typed callbacks and removal on native display."""

import runpy
from pathlib import Path
from unittest.mock import patch

import pygame

from plocks import Event, Sprite, Stage


def main() -> None:
    stages: list[Stage] = []
    root = Path(__file__).parent / "fixtures/games/state_proof"
    with patch.object(Stage, "run", lambda stage: stages.append(stage)):
        game = runpy.run_path(str(root / "main.py"), run_name="__main__")
    stage = stages[0]
    first, second = stage.objects
    assert isinstance(first, Sprite) and isinstance(second, Sprite)
    frozen: list[int] = []

    @stage.on_update
    def exercise(event: Event[Stage, float]) -> None:
        tick = round(stage.time / event.data)
        if tick == 3:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        if tick == 9:
            assert game["first"].state.health == 100 and game["second"].state.health == 40
        if tick == 35:
            assert game["first"].state.speed == game["second"].state.speed == 0.5
            assert game["first"].state.hits == game["second"].state.hits == [10]
            assert game["first"].state.hits is not game["second"].state.hits
            assert (game["first"].state.health, game["second"].state.health) == (90, 30)
            assert (game["stage"].state.score, game["stage"].state.reports) == (2, 2)
            pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        if tick == 40:
            first.stop()
            stage.remove(second)
            frozen.extend((game["first"].state.health, game["second"].state.health))
        if tick == 65:
            assert [game["first"].state.health, game["second"].state.health] == frozen
            assert not stage._actions
            print("STATE_NATIVE_OK", pygame.display.get_driver(), flush=True)
            stage.stop()

    stage.run()
    assert not stage.objects and not stage._actions and stage._target is None
    assert game["stage"].state.score == 2
    print("STATE_NATIVE_CLEANUP_OK", flush=True)


if __name__ == "__main__":
    main()
