"""Measure dialogue draw cost without retaining fonts, layouts or rendered text."""

import json
import platform
import statistics
import time
from pathlib import Path

import pygame
from PIL import Image as PillowImage

from plocks import Actor, Puppet, Sprite, Stage
from plocks._bubbles import _draw_bubble
from plocks._render import frame
from plocks._runtime import close
from plocks._scripts import _step


def main() -> None:
    """Measure cold and repeated draws for small and crowded logical viewports."""
    results: list[dict[str, object]] = []
    for count in (1, 10, 100):
        stage = Stage(640, 400)
        stage._state = "running"
        stage._target = pygame.display.set_mode((640, 400))
        actors: list[Actor] = []
        for index in range(count):
            actor: Actor = (
                Puppet.stick_figure()
                if index % 5 == 4
                else Sprite(PillowImage.new("RGBA", (20, 20), "orange"))
            )
            actor.position = ((index % 10) * 55 - 260, (index // 10) * 30 - 150)
            stage.add(actor)
            actor.say("Hello! This message wraps into readable lines.")
            actors.append(actor)
        _step(stage)
        pygame.font.quit()
        started = time.perf_counter()
        frame(stage)
        cold_ms = (time.perf_counter() - started) * 1000
        drawing: list[float] = []
        frames: list[float] = []
        for _ in range(50):
            started = time.perf_counter()
            for actor in actors:
                _draw_bubble(stage, stage._target, actor)
            drawing.append((time.perf_counter() - started) * 1000)
            started = time.perf_counter()
            frame(stage)
            frames.append((time.perf_counter() - started) * 1000)
        results.append(
            {
                "visible_actors": count,
                "puppets": count // 5,
                "frames": len(frames),
                "cold_frame_ms": cold_ms,
                "bubble_draw_median_ms": statistics.median(drawing),
                "frame_median_ms": statistics.median(frames),
                "frame_p95_ms": sorted(frames)[47],
            }
        )
        close(stage)
    report = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "pygame": pygame.version.ver,
        "display": "SDL dummy",
        "workloads": results,
    }
    path = Path("output/bubbles-performance.json")
    path.write_text(json.dumps(report, indent=2))
    print(path.read_text())


if __name__ == "__main__":
    main()
