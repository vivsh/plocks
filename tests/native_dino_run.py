"""Play Dino Dash on a real desktop display using its normal input handlers."""

import json
import runpy
from pathlib import Path
from typing import cast

import pygame

from plocks import Event, Sprite, Stage


def main() -> None:
    """Check a physical jump, landing, duck, scrolling and final resource cleanup."""
    root = Path(__file__).resolve().parents[1]
    namespace = runpy.run_path(str(root / "src/plocks/_games/dino_run/main.py"))
    stage = cast(Stage, namespace["stage"])
    game = stage._updates[0][1].__globals__
    dino = cast(Sprite, namespace["dino"])
    output = root / "output/playwright"
    output.mkdir(parents=True, exist_ok=True)
    points: dict[str, float | str] = {}

    @stage.on_update
    def exercise(event: Event[Stage, float]) -> None:
        tick = round(stage.time * 60)
        if tick == 10:
            assert dino.body.grounded
            points["ground"] = dino.y
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        if tick == 20:
            assert dino.y > cast(float, points["ground"]) + 40
            points["jump"] = dino.y
            pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))
        if tick == 78:
            assert dino.body.grounded
            points["land"] = dino.y
        if tick == 105:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s))
        if tick == 110:
            assert game["crouching"]
            points["duck"] = dino.image.height
            pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_s))
        if tick == 120:
            assert not game["crouching"] and game["obstacles"] and game["distance"] > 400
            assert stage._target is not None
            pygame.image.save(stage._target, str(output / "dino-dash-native.png"))
            points["driver"] = pygame.display.get_driver()
            stage.stop()

    stage.run()
    assert not stage.objects and not stage._actions and not stage._voices
    assert stage._target is None
    print("NATIVE_DINO_OK", json.dumps(points))


if __name__ == "__main__":
    main()
