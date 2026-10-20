"""Measure native contacts plus authored actions; report timings without adding caches."""

import json
import platform
import statistics
import time

import pygame
from PIL import Image as PillowImage

from plocks import BodyType, Script, Sprite, Stage, TileMap
from plocks._physics import _integrate
from plocks._render import frame
from plocks._runtime import close
from plocks._scripts import _count, _sample, _step


def main() -> None:
    stage = Stage(640, 400, physics=True)
    stage._target = pygame.display.set_mode((640, 400))
    stage._state = "running"
    tile = PillowImage.new("RGBA", (32, 32), "forestgreen")
    stage.add(TileMap(["#" * 20], {"#": tile}, tile_size=(32, 32), solid={"#"}, x=-320, y=-160))
    for index in range(100):
        actor = Sprite(
            PillowImage.new("RGBA", (12, 12), "orange"),
            x=(index % 20) * 25 - 250,
            y=(index // 20) * 20,
        )
        stage.add(actor)
        if index < 20:
            actor.body.force(x=1, seconds=10)
    for index in range(5):
        actor = Sprite(tile, x=index * 100 - 200, y=-100, body_type=BodyType.KINEMATIC)
        stage.add(actor)
        actor.act(Script(Sprite).repeat().glide_by(y=40, seconds=1).glide_by(y=-40, seconds=1))
    samples: list[float] = []
    try:
        for index in range(150):
            started = time.perf_counter()
            _step(stage)
            _integrate(stage, 1 / 60)
            stage._tick += 1
            _sample(stage)
            frame(stage)
            if index >= 30:
                samples.append((time.perf_counter() - started) * 1000)
        print(
            json.dumps(
                {
                    "python": platform.python_version(),
                    "platform": platform.platform(),
                    "display": pygame.display.get_driver(),
                    "bodies": len(stage.physics._bodies),
                    "solid_cells": 20,
                    "fibers": _count(stage),
                    "frames": len(samples),
                    "frame_median_ms": statistics.median(samples),
                    "frame_p95_ms": sorted(samples)[113],
                },
                indent=2,
            )
        )
    finally:
        close(stage)


if __name__ == "__main__":
    main()
