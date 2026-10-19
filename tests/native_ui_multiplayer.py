"""Two-process proof that shared-view input can resume a focused host menu."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from time import monotonic

import pygame

from plocks import Button, Canvas, Event, Label, Multiplayer, ProgressBar, Stage
from plocks._join import configuration, join
from plocks._network import _Client, _Host


def host(folder: Path, port: int) -> None:
    """Keep UI responsive while simulation is paused, then stream its changed pixels."""
    stage = Stage(width=320, height=240)
    label = Label("Paused", position=(0, 90))
    button = Button("Continue")
    bar = ProgressBar(value=0, position=(0, 60), width=100, color="#008000")
    for control in (label, button, bar):
        stage.add(control)
    stage.focus(button)
    started = monotonic()

    @button.on_click
    def resume(event: Event[Button, None]) -> None:
        label.text = "Playing"
        bar.value = 100
        button.visible = False
        stage.resume()

    @stage.on_start
    def ready(event: Event[Stage, None]) -> None:
        stage.pause()
        owner = stage._network
        assert isinstance(owner, _Host)
        (folder / "ready.json").write_text(json.dumps({"code": owner.connection_code}))

    @stage.on_draw
    def stop(canvas: Canvas) -> None:
        if monotonic() - started > 3:
            stage.stop()

    stage.run(multiplayer=Multiplayer(slots=(1,), bind="127.0.0.1", port=port))
    assert label.text == "Playing" and stage.time > 0
    assert stage._network is None and stage.focused_button is None
    (folder / "host-ui.json").write_text(json.dumps({"resumed": True, "time": stage.time}))


def client(folder: Path, port: int) -> None:
    """Send native mapped input and inspect the decoded host's actual UI pixels."""
    from unittest.mock import patch

    code = json.loads((folder / "ready.json").read_text())["code"]
    stage = Stage()
    started = monotonic()
    sent = False
    seen = False

    @stage.on_draw
    def observe(canvas: Canvas) -> None:
        nonlocal sent, seen
        owner = stage._network
        assert isinstance(owner, _Client)
        if owner.control.phase == "active" and not sent:
            sent = True
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
            pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))
        if owner.frame is not None and owner.frame.get_at((160, 60))[:3] == (0, 128, 0):
            seen = True
            pygame.image.save(owner.frame, str(folder / "remote-ui.png"))
            stage.stop()
        if monotonic() - started > 2:
            if owner.frame is not None:
                pygame.image.save(owner.frame, str(folder / "last-remote-ui.png"))
            stage.stop()

    with patch("plocks._join.Stage", return_value=stage):
        join(configuration("127.0.0.1", port, 2, code))
    assert sent and seen and stage._network is None, (sent, seen)
    (folder / "client-ui.json").write_text(json.dumps({"ui_seen": seen}))


if __name__ == "__main__":
    mode, directory, port_text = sys.argv[1:]
    if mode == "--host":
        host(Path(directory), int(port_text))
    else:
        client(Path(directory), int(port_text))
