"""Play the actual bundled foundation examples; also exercise installed wheels."""

from __future__ import annotations

import argparse
import json
import runpy
from importlib.resources import as_file, files
from itertools import pairwise
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import cast

import pygame

from plocks import Button, Canvas, Event, Hinge, Label, Motor, Rope, Sprite, Stage
from plocks._connections import _anchors


def exercise(name: str, output: Path) -> dict[str, object]:
    """Drive real input through one static-artwork example and save its rendered view."""
    with as_file(files("plocks").joinpath("_games", name, "main.py")) as entry:
        namespace = cast(dict[str, object], runpy.run_path(str(entry)))
    stage = namespace["stage"]
    assert isinstance(stage, Stage)
    sent: set[str] = set()
    frames: list[float] = []
    deadline = perf_counter() + 10
    report: dict[str, object] = {"example": name}
    initial_cart = next(
        (
            obj.x
            for obj in stage.objects
            if isinstance(obj, Sprite) and obj.image.width == 100 and obj.image.height == 18
        ),
        None,
    )

    @stage.on_update
    def play(event: Event[Stage, float]) -> None:
        if "start" not in sent:
            sent.add("start")
            if name == "maze_quest":
                coin = namespace["coin"]
                # The first authored coin is accessible from the touch subscriptions.
                assert isinstance(coin, Sprite)
                first = stage._touches[0].other
                assert isinstance(first, Sprite)
                pygame.event.post(
                    pygame.event.Event(
                        pygame.MOUSEBUTTONDOWN, button=1, pos=stage.to_screen(first.position)
                    )
                )
            elif name == "robot_workshop":
                for key in (pygame.K_RIGHT, pygame.K_SPACE):
                    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
        if name == "swing_lab":
            rope = namespace["rope"]
            assert isinstance(rope, Rope)
            if stage.time >= 0.2 and "cut" not in sent:
                sent.add("cut")
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
            if stage.time >= 0.4 and "reset" not in sent:
                assert not rope.connected
                sent.add("reset")
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
        if name == "maze_quest" and stage.time >= 1.7 and "pause" not in sent:
            score = namespace["score"]
            assert isinstance(score, Label) and score.text == "Coins: 1 / 4"
            sent.add("pause")
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p))

    @stage.on_draw
    def inspect(canvas: Canvas) -> None:
        assert perf_counter() < deadline, f"{name} stopped progressing"
        frames.append(perf_counter())
        if stage.paused and name == "maze_quest" and "resume" not in sent:
            sent.add("resume")
            button = namespace["resume"]
            assert isinstance(button, Button) and stage.focused_button is button
            pygame.event.post(
                pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    button=1,
                    pos=stage.to_screen(button.position, world=False),
                )
            )
        end = 2.0 if name == "maze_quest" else 0.8
        if stage.time < end:
            return
        if name == "maze_quest":
            assert {"pause", "resume"} <= sent and not stage.paused
            report["collected_and_menu_resumed"] = True
        elif name == "swing_lab":
            assert any(
                isinstance(link, Rope) and link.connected for link in stage.physics._connections
            )
            assert {"cut", "reset"} <= sent
            report["cut_and_reset"] = True
        else:
            assert initial_cart is not None
            chassis = next(
                obj
                for obj in stage.objects
                if isinstance(obj, Sprite) and obj.image.width == 100 and obj.image.height == 18
            )
            assert chassis.x > initial_cart + 5
            assert any(
                isinstance(link, Motor) and link.speed > 0 for link in stage.physics._connections
            )
            errors = []
            for link in stage.physics._connections:
                if isinstance(link, Hinge):
                    a, b = _anchors(link)
                    errors.append(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)
            report["cart_distance"] = chassis.x - initial_cart
            report["maximum_hinge_error"] = max(errors)
        assert stage._target is not None
        pygame.image.save(stage._target, str(output / f"{name}.png"))
        report["driver"] = pygame.display.get_driver()
        report["frames"] = len(frames)
        report["mean_render_interval_ms"] = mean(b - a for a, b in pairwise(frames)) * 1000
        stage.stop()

    stage.run()
    assert not stage.objects and not stage._actions and not stage._touches
    if stage._physics is not None:
        assert not stage.physics._bodies and not stage.physics._connections
    return report


def main() -> None:
    """Write bounded scenario results and screenshots into an explicitly supplied folder."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = [
        exercise(name, args.output) for name in ("maze_quest", "swing_lab", "robot_workshop")
    ]
    (args.output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
