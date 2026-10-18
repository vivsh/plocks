"""Protocol/source failures are observed before they can corrupt player input."""

from __future__ import annotations

import selectors
import socket
from collections.abc import Iterator

import pygame
import pytest

from plocks import GamepadButton, GamepadInput, Key, Multiplayer, NetworkError, RemoteChange, Stage
from plocks._gamepads import _apply
from plocks._runtime import close

pytest.importorskip("msgspec")
pytest.importorskip("websockets")

from websockets.protocol import State
from websockets.server import ServerProtocol

from plocks._network import (
    _Connection,
    _decode_frame,
    _health,
    _Host,
    _host_packet,
    _lost,
    _RemotePeer,
    capture,
    pump,
)
from plocks._network_protocol import VERSION, Frame, FrameRequest, Hello, Input, ViewHello


@pytest.fixture
def world() -> Iterator[tuple[Stage, _Host]]:
    """Own every transport resource even if a validation assertion fails."""
    stage = Stage(gamepad_count=3)
    owner = _Host(
        Multiplayer(slots=(1, 2)),
        socket.socket(),
        selectors.DefaultSelector(),
        "safe-code",
        [],
        [],
        0,
        0,
    )
    stage._network, stage._state = owner, "running"
    try:
        yield stage, owner
    finally:
        close(stage)


def incoming(owner: _Host) -> _RemotePeer:
    """A protocol-only accepted connection requires no bound socket or worker."""
    connection = _Connection(
        None, ServerProtocol(state=State.OPEN), "hello", 0, 0, None, [], bytearray()
    )
    peer = _RemotePeer(connection, None, -1, (0, 60), "")
    owner.peers.append(peer)
    return peer


@pytest.mark.parametrize("code", ["incorrect", "😀", "x" * 129])
def test_wrong_codes_do_not_claim_a_slot(world: tuple[Stage, _Host], code: str) -> None:
    """Invalid/unicode authorization cannot crash the game or claim another player."""
    stage, owner = world
    peer = incoming(owner)
    with pytest.raises(NetworkError, match="code or protocol"):
        _host_packet(stage, owner, peer.connection, Hello(VERSION, code, 1), 0)
    assert peer.slot is None and not stage.gamepads[1].remote_connected


def test_slot_claims_are_exclusive(world: tuple[Stage, _Host]) -> None:
    """A second peer cannot replace an authorized remote player's slot."""
    stage, owner = world
    first, second = incoming(owner), incoming(owner)
    _host_packet(stage, owner, first.connection, Hello(VERSION, "safe-code", 1), 0)
    with pytest.raises(NetworkError, match="already connected"):
        _host_packet(stage, owner, second.connection, Hello(VERSION, "safe-code", 1), 0)
    assert first.slot == 1 and second.slot is None
    with pytest.raises(NetworkError, match="not reserved"):
        _host_packet(stage, owner, second.connection, Hello(VERSION, "safe-code", 0), 0)


def test_neutral_and_first_view_are_required(world: tuple[Stage, _Host]) -> None:
    """TCP/authentication alone never enables blind gameplay or a connected event."""
    stage, owner = world
    peer = incoming(owner)
    _host_packet(stage, owner, peer.connection, Hello(VERSION, "safe-code", 1), 0)
    _host_packet(stage, owner, peer.connection, Input(0, GamepadInput()), 0)
    assert not stage.gamepads[1].remote_connected
    view = incoming(owner)
    _host_packet(stage, owner, view.connection, ViewHello(VERSION, peer.session_key), 0)
    _host_packet(stage, owner, view.connection, FrameRequest(None), 0)
    stage._target = pygame.Surface((stage.width, stage.height))
    capture(stage, 0)
    assert owner.views[0].last_sent_frame == 0 and not stage._pending
    assert owner.views[0].sent_at == 0
    _host_packet(stage, owner, view.connection, FrameRequest(0), 0.1)
    assert owner.views[0].sent_at is None
    assert stage.gamepads[1].remote_connected
    assert stage._pending == [RemoteChange(1, True, None)]


def test_invalid_input_and_disconnect_leave_neutral_controls(world: tuple[Stage, _Host]) -> None:
    """A disconnected remote cannot leave keys, repeats, or a reusable slot held."""
    stage, owner = world
    peer = incoming(owner)
    peer.slot, peer.connection.phase = 1, "active"
    stage._held_keys.add(Key.ENTER)
    assert not stage.gamepads[1].is_down(GamepadButton.A)
    _apply(stage.gamepads[1], GamepadInput(buttons=frozenset({GamepadButton.A})))
    assert stage.gamepads[1].is_down(GamepadButton.A)
    with pytest.raises(NetworkError, match="sequence"):
        _host_packet(stage, owner, peer.connection, Input(4, GamepadInput()), 0)
    _lost(stage, owner, peer.connection, "test disconnect")
    assert not owner.peers and not stage.gamepads[1].is_down(GamepadButton.A)
    assert stage._pending == [RemoteChange(1, False, "test disconnect")]


def test_input_rate_and_timeouts_are_bounded(world: tuple[Stage, _Host]) -> None:
    """Flooding cannot silently expand buffers or indefinitely defer health failures."""
    stage, owner = world
    peer = incoming(owner)
    peer.slot, peer.connection.phase = 1, "active"
    for sequence in range(60):
        _host_packet(stage, owner, peer.connection, Input(sequence, GamepadInput()), 0)
    with pytest.raises(NetworkError, match="rate"):
        _host_packet(stage, owner, peer.connection, Input(60, GamepadInput()), 0)
    peer.connection.phase = "handshake"
    peer.connection.socket = socket.socket()
    with pytest.raises(NetworkError, match="stale"):
        _health(peer.connection, 6)
    peer.connection.outgoing.clear()
    with pytest.raises(NetworkError, match="timed out"):
        _health(peer.connection, 6)


def test_remote_players_keep_independent_controls(world: tuple[Stage, _Host]) -> None:
    """Dropping one player neutralizes only that slot, leaving another remote active."""
    stage, owner = world
    first, second = incoming(owner), incoming(owner)
    for peer, slot in ((first, 1), (second, 2)):
        _host_packet(stage, owner, peer.connection, Hello(VERSION, "safe-code", slot), 0)
        peer.connection.phase = "active"
    _host_packet(stage, owner, first.connection, Input(0, GamepadInput(left_stick=(1, 0))), 0)
    _host_packet(stage, owner, second.connection, Input(0, GamepadInput(left_stick=(-1, 0))), 0)
    assert stage.gamepads[1].left_stick == (1, 0)
    assert stage.gamepads[2].left_stick == (-1, 0)
    _lost(stage, owner, first.connection, "first left")
    assert stage.gamepads[1].left_stick == (0, 0)
    assert stage.gamepads[2].remote_connected and stage.gamepads[2].left_stick == (-1, 0)


def test_view_deadline_does_not_trust_heartbeats(world: tuple[Stage, _Host]) -> None:
    """A responsive socket cannot keep blind controls active without displayed-frame ACKs."""
    stage, owner = world
    peer = incoming(owner)
    _host_packet(stage, owner, peer.connection, Hello(VERSION, "safe-code", 1), 0)
    _host_packet(stage, owner, peer.connection, Input(0, GamepadInput()), 0)
    view = incoming(owner)
    _host_packet(stage, owner, view.connection, ViewHello(VERSION, peer.session_key), 0)
    _host_packet(stage, owner, view.connection, FrameRequest(None), 0)
    stage._target = pygame.Surface((stage.width, stage.height))
    capture(stage, 0)
    _host_packet(stage, owner, view.connection, FrameRequest(0), 0.1)
    _host_packet(stage, owner, peer.connection, Input(1, GamepadInput(left_stick=(1, 0))), 0.1)
    view.connection.outgoing.clear()
    capture(stage, 0.2)
    assert owner.views[0].sent_at == 0.2
    other = incoming(owner)
    _host_packet(stage, owner, other.connection, Hello(VERSION, "safe-code", 2), 0.2)
    _host_packet(stage, owner, other.connection, Input(0, GamepadInput()), 0.2)
    other_view = incoming(owner)
    _host_packet(stage, owner, other_view.connection, ViewHello(VERSION, other.session_key), 0.2)
    _host_packet(stage, owner, other_view.connection, FrameRequest(None), 0.2)
    capture(stage, 0.4)
    _host_packet(stage, owner, other_view.connection, FrameRequest(2), 0.5)
    peer.connection.last_received = view.connection.last_received = 1.1
    pump(stage, 1.1)
    assert stage.gamepads[1].remote_connected
    pump(stage, 1.21)
    assert owner.peers == [other] and len(owner.views) == 1
    assert stage.gamepads[2].remote_connected
    assert not stage.gamepads[1].remote_connected
    assert stage.gamepads[1].left_stick == (0, 0)
    assert any(
        isinstance(event, RemoteChange)
        and event.reason is not None
        and "acknowledgement" in event.reason
        for event in stage._pending
    )


def test_acknowledged_view_has_no_expired_deadline(world: tuple[Stage, _Host]) -> None:
    """Acknowledging the displayed frame releases its deadline before another is sent."""
    stage, owner = world
    peer = incoming(owner)
    _host_packet(stage, owner, peer.connection, Hello(VERSION, "safe-code", 1), 0)
    _host_packet(stage, owner, peer.connection, Input(0, GamepadInput()), 0)
    view = incoming(owner)
    _host_packet(stage, owner, view.connection, ViewHello(VERSION, peer.session_key), 0)
    _host_packet(stage, owner, view.connection, FrameRequest(None), 0)
    stage._target = pygame.Surface((stage.width, stage.height))
    capture(stage, 0)
    _host_packet(stage, owner, view.connection, FrameRequest(0), 0.1)
    pump(stage, 2)
    assert stage.gamepads[1].remote_connected
    assert len(owner.views) == 1 and owner.views[0].sent_at is None


def test_frame_pixels_are_lossless_and_actual_image_bounds_are_checked() -> None:
    """A forged PNG cannot evade allocation bounds by declaring a tiny logical viewport."""
    import io
    import struct
    import zlib

    from PIL import Image

    stream = io.BytesIO()
    Image.new("RGBA", (1, 1), (20, 40, 60, 255)).save(stream, format="PNG")
    packet = Frame(0, 0, False, (1, 1), stream.getvalue())
    assert tuple(_decode_frame(packet).get_at((0, 0))) == (20, 40, 60, 255)
    with pytest.raises(NetworkError, match="format rejected"):
        _decode_frame(Frame(0, 0, False, (2, 2), stream.getvalue()))
    forged = bytearray(stream.getvalue())
    forged[16:24] = struct.pack(">II", 1_000_000, 1_000_000)
    forged[29:33] = struct.pack(">I", zlib.crc32(forged[12:29]))
    with pytest.raises(NetworkError, match="safely decoded"):
        _decode_frame(Frame(0, 0, False, (1, 1), bytes(forged)))
