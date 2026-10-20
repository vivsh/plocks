"""Two-process shared-score/jump probe; run with --host or --join and a temp folder."""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

import pygame

from plocks import (
    BodyType,
    Bounds,
    Canvas,
    Event,
    GamepadButton,
    GamepadPress,
    Image,
    Multiplayer,
    Sprite,
    Stage,
    TileMap,
)
from plocks._network import _Client, _Host


@dataclass
class Scores:
    score: int = 0
    local: int = 0


def host(folder: Path, port: int) -> None:
    """Host owns score/physics; its Canvas pixels are the remote score evidence."""
    assets = Path(str(files("plocks").joinpath("_games/platformer/assets")))
    stage = Stage(gamepad_count=2, physics=True, state=Scores)
    hero = Sprite(assets / "hero.png")
    friend = Sprite(assets / "checkpoint.png", body_type=BodyType.KINEMATIC)
    hero.position, friend.position = (0, -20), (-100, 60)
    stage.add(hero)
    stage.add(friend)
    stage.add(
        TileMap(
            rows=["########"],
            palette={"#": Image(assets / "grass.png")},
            tile_size=(32, 32),
            solid={"#"},
            x=-128,
            y=-60,
        )
    )
    started = time.monotonic()
    peak = hero.y
    focus_restores = 0

    @stage.on_start
    def ready(event: Event[Stage[Scores], None]) -> None:
        owner = stage._network
        assert isinstance(owner, _Host)
        (folder / "ready.json").write_text(json.dumps({"code": owner.connection_code}))
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d))

    @stage.on_button_down(GamepadButton.A)
    def jump(event: Event[Stage[Scores], GamepadPress]) -> None:
        if event.data.gamepad.index == 0:
            event.target.state.local += 1
        else:
            event.target.state.score += 1
            if hero.body.grounded:
                hero.body.impulse(y=300)

    @stage.on_update
    def update(event: Event[Stage[Scores], float]) -> None:
        nonlocal peak
        hero.body.velocity = (stage.gamepads[1].left_stick[0] * 80, hero.body.velocity[1])
        friend.x += stage.gamepads[0].left_stick[0] * event.data * 10
        peak = max(peak, hero.y)

    @stage.on_draw
    def draw(canvas: Canvas) -> None:
        nonlocal focus_restores
        if os.environ.get("PLOCKS_NATIVE_FOCUS_PROBE") == "1" and "focus" in stage._pause_reasons:
            pygame.event.post(pygame.event.Event(pygame.WINDOWFOCUSGAINED))
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d))
            focus_restores += 1
        canvas.text(f"Local: {stage.state.local}   Remote: {stage.state.score}", (-220, 160))
        color = (stage.state.score, 255, 0) if stage.state.score else (255, 0, 0)
        canvas.rectangle(Bounds(-220, 100, -190, 130), color=color)
        canvas.rectangle(
            Bounds(-180, 100, -150, 130), color=(0, 128, 255) if stage.state.local else "black"
        )
        if time.monotonic() - started > 4:
            stage.stop()

    stage.run(multiplayer=Multiplayer(slots=(1,), bind="127.0.0.1", port=port))
    (folder / "host.json").write_text(
        json.dumps(
            {
                "score": stage.state.score,
                "local_score": stage.state.local,
                "friend_x": friend.x,
                "hero_x": hero.x,
                "peak": peak,
                "network_closed": stage._network is None,
                "synthetic_focus_restores": focus_restores,
            }
        )
    )


def client(folder: Path, port: int, *, bad_code: bool = False) -> None:
    """Send a real native key transition and inspect the actual decoded score pixel."""
    code = json.loads((folder / "ready.json").read_text())["code"]
    stage = Stage(width=640, height=480, gamepad_count=1)
    started = time.monotonic()
    pressed = False
    score_seen = False
    local_score_seen = False
    frames: set[int] = set()
    frame_times: list[float] = []
    sent: list[float] = []
    latencies: list[float] = []
    neutral_blocked = False

    @stage.on_start
    def hold_during_connection(event: Event[Stage, None]) -> None:
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))

    @stage.on_draw
    def draw(canvas: Canvas) -> None:
        nonlocal pressed, score_seen, local_score_seen, neutral_blocked
        owner = stage._network
        assert isinstance(owner, _Client)
        if owner.control.phase == "neutral":
            neutral_blocked = True
            if time.monotonic() - started > 0.25:
                pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))
        if owner.frame is not None:
            local_score_seen |= owner.frame.get_at((65, 55))[:3] == (0, 128, 255)
            if owner.frame_sequence is not None:
                if owner.frame_sequence not in frames:
                    frame_times.append(time.monotonic())
                frames.add(owner.frame_sequence)
            red, green, _, _ = owner.frame.get_at((25, 55))
            if green == 255 and red > 0:
                score_seen = True
                while len(latencies) < red:
                    latencies.append(time.monotonic() - sent[len(latencies)])
            if score_seen and red == len(sent):
                pygame.image.save(owner.frame, str(folder / "shared-score.png"))
        if (
            owner.control.phase == "active"
            and len(sent) < 8
            and (not sent or time.monotonic() - sent[-1] > 0.15)
        ):
            pressed = True
            sent.append(time.monotonic())
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
            pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d))
        if time.monotonic() - started > 2.8:
            stage.stop()

    from plocks.cli import main

    argv = ["plocks", "join", "127.0.0.1", "--player", "2", "--port", str(port)]
    with (
        patch("plocks._join.Stage", return_value=stage),
        patch("builtins.input", return_value="incorrect-code" if bad_code else code),
        patch.object(sys, "argv", argv),
    ):
        result = main()
    assert result == (1 if bad_code else 0)
    (folder / ("rejected-client.json" if bad_code else "client.json")).write_text(
        json.dumps(
            {
                "score_seen": score_seen,
                "local_score_seen": local_score_seen,
                "frames": len(frames),
                "pressed": pressed,
                "network_closed": stage._network is None,
                "visible_responses": len(latencies),
                "neutral_blocked": neutral_blocked,
                "p95_visible_ms": sorted(latencies)[int(0.95 * (len(latencies) - 1))] * 1000
                if latencies
                else None,
                "remote_fps": (len(frame_times) - 1) / (frame_times[-1] - frame_times[0])
                if len(frame_times) > 1
                else 0,
            }
        )
    )


if __name__ == "__main__":
    mode, directory, port_text = sys.argv[1:]
    if mode == "--host":
        host(Path(directory), int(port_text))
    else:
        client(Path(directory), int(port_text), bad_code=mode == "--bad-code")
