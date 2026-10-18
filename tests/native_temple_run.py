"""Play Temple Trail through a native SDL window with posted keyboard events."""

import runpy
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pygame

from plocks import Event, Sprite, Stage


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "output/playwright"
    output.mkdir(parents=True, exist_ok=True)
    stages: list[Stage] = []

    def capture(stage: Stage) -> None:
        stages.append(stage)

    with patch.object(Stage, "run", capture):
        runpy.run_path(str(root / "src/plocks/_games/temple_run/main.py"), run_name="__main__")
    stage = stages[0]
    update = stage._updates[0][1]
    captured: set[str] = set()

    @stage.on_update
    def exercise(event: Event[Stage, float]) -> None:
        values = update.__globals__
        hero = cast(Sprite, values["hero"])
        objects = cast(list[tuple[Sprite, int, int, str]], values["objects"])
        distance = cast(float, values["distance"])
        if objects:
            _, location, lane, kind = objects[0]
            ahead = location - distance
            key = None
            if kind == "coin" and hero.x != lane * 145:
                key = pygame.K_RIGHT if hero.x < lane * 145 else pygame.K_LEFT
            elif kind == "hurdle" and 30 < ahead <= 34:
                key = pygame.K_SPACE
            elif kind == "arch" and 42 < ahead <= 46:
                key = pygame.K_DOWN
            elif kind in ("left", "right") and ahead <= 45:
                key = pygame.K_LEFT if kind == "left" else pygame.K_RIGHT
            if key is not None:
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
                pygame.event.post(pygame.event.Event(pygame.KEYUP, key=key))
        for label, start in (("jump", 220), ("slide", 462), ("turn", 610)):
            if distance >= start and label not in captured:
                target = stage._target
                assert target is not None
                pygame.image.save(target, str(output / f"temple-native-{label}.png"))
                captured.add(label)
        if values["outcome"] != "playing":
            assert values["outcome"] == "Temple reached! Well run.", values
            assert values["score"] == 8
            print("TEMPLE_NATIVE_OK", pygame.display.get_driver(), values["score"], flush=True)
            stage.stop()
        assert stage.time < 30, "Native course timed out"

    stage.run()
    assert not stage.objects and not stage._actions and stage._target is None


if __name__ == "__main__":
    main()
