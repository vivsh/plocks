"""Input/view ownership, packet validation, and separate-process loopback proof."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from plocks import GamepadButton, GamepadInput, Multiplayer


def test_configuration_is_explicit_and_immutable() -> None:
    """Bad slots/addresses/ports fail before any socket or game is acquired."""
    for slots in ((), (1, 1), (-1,), (True,)):
        with pytest.raises(ValueError):
            Multiplayer(slots=slots)
    for port in (0, 65536, True):
        with pytest.raises(ValueError):
            Multiplayer(port=port)
    with pytest.raises(ValueError):
        Multiplayer(bind="my-computer.local")


def test_input_rejects_invalid_values() -> None:
    """An invalid automated/remote sample cannot corrupt held-input state."""
    assert GamepadInput(buttons=frozenset({GamepadButton.A})).left_stick == (0, 0)
    for stick in ((float("nan"), 0), (1, 1), (float("inf"), 0)):
        with pytest.raises(ValueError):
            GamepadInput(left_stick=stick)
    with pytest.raises(ValueError):
        GamepadInput(left_trigger=1.1)


def test_closed_wire_protocol() -> None:
    """Only a tagged, typed known message can enter the input path."""
    pytest.importorskip("msgspec")
    import msgspec

    from plocks._network_protocol import Input, decode, encode

    sample = Input(1, GamepadInput(buttons=frozenset({GamepadButton.A})))
    assert decode(encode(sample)) == sample
    with pytest.raises(msgspec.DecodeError):
        decode(msgspec.msgpack.encode({"type": "RunPython", "code": "print(1)"}))


def test_two_processes_share_score_and_physics(tmp_path: Path) -> None:
    """A remote tap jumps and changes the actual Canvas pixels, then releases sockets."""
    pytest.importorskip("websockets")
    pytest.importorskip("msgspec")
    probe = Path(__file__).with_name("native_multiplayer.py")
    with socket.socket() as reserve:
        reserve.bind(("127.0.0.1", 0))
        port = reserve.getsockname()[1]
    command = [sys.executable, "-u", str(probe)]
    env = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
    host = subprocess.Popen(
        [*command, "--host", str(tmp_path), str(port)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.monotonic() + 5
        while not (tmp_path / "ready.json").exists() and host.poll() is None:
            if time.monotonic() >= deadline:
                pytest.fail("Host did not become ready within five seconds")
            time.sleep(0.02)
        if not (tmp_path / "ready.json").exists():
            pytest.fail(host.communicate(timeout=1)[0])
        rejected = subprocess.run(
            [*command, "--bad-code", str(tmp_path), str(port)],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        assert rejected.returncode == 0, rejected.stdout + rejected.stderr
        assert "Joining code or protocol version rejected" in rejected.stderr
        client = subprocess.run(
            [*command, "--join", str(tmp_path), str(port)],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        output = host.communicate(timeout=8)[0]
        assert client.returncode == 0, client.stdout + client.stderr
        assert host.returncode == 0, output
        one = json.loads((tmp_path / "host.json").read_text())
        two = json.loads((tmp_path / "client.json").read_text())
        assert one["score"] == 8 and two["score_seen"]
        assert one["local_score"] == 1 and two["local_score_seen"]
        assert one["hero_x"] > 0 and one["peak"] > 0
        assert one["friend_x"] > -90
        assert two["frames"] >= 8
        assert two["visible_responses"] == 8
        assert two["neutral_blocked"]
        # Hardware-dependent FPS/latency are recorded separately from CI correctness.
        assert one["network_closed"] and two["network_closed"]
        assert (tmp_path / "shared-score.png").is_file()
    finally:
        if host.poll() is None:
            host.kill()
            host.wait()
