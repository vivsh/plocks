"""Bounded, main-thread multiplayer I/O; gameplay state remains on Stage/Gamepad."""

from __future__ import annotations

import errno
import io
import secrets
import selectors
import socket
import sys
import time
from dataclasses import dataclass
from ipaddress import ip_address
from typing import TYPE_CHECKING

import msgspec
import pygame
from PIL import Image
from websockets.client import ClientProtocol
from websockets.exceptions import WebSocketException
from websockets.frames import Frame as WebFrame
from websockets.frames import Opcode
from websockets.http11 import Request, Response
from websockets.protocol import State
from websockets.server import ServerProtocol
from websockets.uri import parse_uri

from ._gamepads import _apply, _sample
from ._network_protocol import (
    CONTROL_LIMIT,
    MAX_FRAME,
    MAX_SIZE,
    VERSION,
    Accepted,
    Frame,
    FrameRequest,
    Hello,
    Input,
    Packet,
    ViewHello,
    Welcome,
    decode,
    encode,
)
from .errors import NetworkError
from .events import GamepadPress, RemoteChange
from .gamepads import Gamepad, GamepadInput
from .multiplayer import Multiplayer

if TYPE_CHECKING:
    from .stage import Stage


@dataclass(slots=True)
class _Connection:
    socket: socket.socket | None
    protocol: ServerProtocol | ClientProtocol
    phase: str
    phase_started: float
    last_received: float
    pending_ping: tuple[bytes, float] | None
    outgoing: list[tuple[float, memoryview]]
    incoming_fragment: bytearray


@dataclass(slots=True)
class _RemotePeer:
    connection: _Connection
    slot: int | None
    last_sequence: int
    input_window: tuple[float, float]
    session_key: str


@dataclass(slots=True)
class _ViewPeer:
    connection: _Connection
    owner: _RemotePeer | None
    requested: bool
    last_sent_frame: int | None
    sent_at: float | None = None


@dataclass(slots=True)
class _Host:
    settings: Multiplayer
    listener: socket.socket
    selector: selectors.BaseSelector
    connection_code: str
    peers: list[_RemotePeer]
    views: list[_ViewPeer]
    next_frame_sequence: int
    next_capture_at: float


@dataclass(slots=True)
class _Client:
    control: _Connection
    view: _Connection | None
    selector: selectors.BaseSelector
    requested_slot: int
    connection_code: str
    session_key: str
    next_input_sequence: int
    last_accepted: int
    last_acceptance_time: float
    frame: pygame.Surface | None
    frame_sequence: int | None
    frame_received_at: float


@dataclass(frozen=True, slots=True)
class _JoinConfig:
    address: str
    port: int
    slot: int
    connection_code: str


def _phase(connection: _Connection, phase: str, now: float) -> None:
    connection.phase, connection.phase_started = phase, now


def _host(stage: Stage, settings: Multiplayer) -> _Host:
    """Acquire a listener atomically; no game starts on a partially opened host."""
    if max(settings.slots) >= len(stage.gamepads):
        raise ValueError("Remote slot does not exist; increase gamepad_count")
    if stage.width > MAX_SIZE[0] or stage.height > MAX_SIZE[1]:
        raise ValueError("Multiplayer supports logical viewports up to 1280x720")
    listener = socket.socket(socket.AF_INET6 if ":" in settings.bind else socket.AF_INET)
    selector = selectors.DefaultSelector()
    try:
        if sys.platform == "win32":
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((settings.bind, settings.port))
        listener.listen(4)
        listener.setblocking(False)
        selector.register(listener, selectors.EVENT_READ)
    except OSError as error:
        listener.close()
        selector.close()
        raise NetworkError(f"Cannot host on {settings.bind}:{settings.port}: {error}") from error
    host = _Host(settings, listener, selector, secrets.token_urlsafe(18), [], [], 0, 0.0)
    print(f"Plocks multiplayer port {settings.port}; players {[x + 1 for x in settings.slots]}")
    print(f"Connection code: {host.connection_code}\nAudio plays on the host only.")
    if settings.bind in ("0.0.0.0", "::"):
        print(
            "Join using this computer's numeric LAN address from network settings, not the wildcard bind address."
        )
    else:
        print(f"Join address: {settings.bind}")
    return host


def _connect(
    selector: selectors.BaseSelector, address: str, port: int, *, view: bool = False
) -> _Connection:
    ip_address(address)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Port must be in 1..65535")
    sock = socket.socket(socket.AF_INET6 if ":" in address else socket.AF_INET)
    host = f"[{address}]" if ":" in address else address
    protocol = ClientProtocol(
        parse_uri(f"ws://{host}:{port}/"),
        max_size=MAX_FRAME + CONTROL_LIMIT if view else CONTROL_LIMIT,
    )
    now = time.monotonic()
    connection = _Connection(sock, protocol, "connecting", now, now, None, [], bytearray())
    try:
        sock.setblocking(False)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        result = sock.connect_ex((address, port))
        if result not in (0, errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EALREADY):
            raise OSError(result, "Connection refused or unavailable")
        selector.register(sock, selectors.EVENT_READ | selectors.EVENT_WRITE, connection)
    except BaseException:
        sock.close()
        raise
    return connection


def _client(config: _JoinConfig) -> _Client:
    selector = selectors.DefaultSelector()
    try:
        connection = _connect(selector, config.address, config.port)
    except BaseException:
        selector.close()
        raise
    return _Client(
        connection,
        None,
        selector,
        config.slot,
        config.connection_code,
        "",
        0,
        -1,
        time.monotonic(),
        None,
        None,
        0.0,
    )


def nonlocal_slot(slot: Gamepad) -> bool:
    """Derive source selection without another source map on Gamepad."""

    stage: Stage = slot._stage
    return isinstance(stage._network, _Host) and slot.index in stage._network.settings.slots


def remote_connected(slot: Gamepad) -> bool:
    owner = slot._stage._network
    return isinstance(owner, _Host) and any(
        peer.slot == slot.index and peer.connection.phase == "active" for peer in owner.peers
    )


def _queue(connection: _Connection, packet: Packet, now: float) -> None:
    connection.protocol.send_binary(encode(packet))
    _collect(connection, now)
    if not isinstance(packet, Frame) and sum(len(data) for _, data in connection.outgoing) > 65536:
        raise NetworkError("Control connection buffer exceeded 64 KiB")


def _collect(connection: _Connection, now: float) -> None:
    for chunk in connection.protocol.data_to_send():
        if chunk:
            connection.outgoing.append((now, memoryview(chunk)))
    limit = MAX_FRAME + CONTROL_LIMIT
    if sum(len(data) for _, data in connection.outgoing) > limit:
        raise NetworkError("Outgoing connection buffer exceeded its limit")


def _retire(selector: selectors.BaseSelector, connection: _Connection) -> None:
    sock, connection.socket = connection.socket, None
    connection.phase = "closed"
    connection.outgoing.clear()
    connection.incoming_fragment.clear()
    if sock is not None:
        try:
            selector.unregister(sock)
        except KeyError:
            pass
        finally:
            sock.close()


def _closing(connection: _Connection, reason: str) -> None:
    """Attempt a nonblocking close notice; peer failure still has a finite deadline.

    Already queued bytes retain order. An unavailable socket cannot guarantee a
    delivered reason; the other side then reports closure or its health timeout.
    """
    if connection.socket is None or connection.protocol.state not in (State.OPEN, State.CLOSING):
        return
    try:
        text = reason.encode("utf-8")[:120].decode("utf-8", errors="ignore")
        if connection.protocol.state is State.OPEN:
            connection.protocol.send_close(1000 if reason == "Session closed" else 1008, text)
        _collect(connection, time.monotonic())
        _write(connection)
    except (OSError, NetworkError, WebSocketException):
        # This is best-effort error reporting; retirement always releases the socket.
        return


def _lost(stage: Stage, host: _Host, connection: _Connection, reason: str) -> None:
    """Retire both channels and pending presses before a slot can be reused."""
    for secret in (host.connection_code, *(peer.session_key for peer in host.peers)):
        if secret:
            reason = reason.replace(secret, "[redacted]")
    _closing(connection, reason)
    peer = next((p for p in host.peers if p.connection is connection), None)
    view = next((v for v in host.views if v.connection is connection), None)
    if peer is None and view is not None:
        peer = view.owner
    if peer is not None:
        active = peer.connection.phase == "active"
        if peer.slot is not None:
            slot = stage.gamepads[peer.slot]
            _apply(slot, GamepadInput(), baseline=True)
            stage._pending[:] = [
                event
                for event in stage._pending
                if not isinstance(event, GamepadPress) or event.gamepad is not slot
            ]
            from ._gamepads import _rebaseline

            _rebaseline(slot)
            stage._pending.append(RemoteChange(peer.slot, False, reason))
            label = "disconnected" if active else "could not finish joining"
            print(f"Player {peer.slot + 1} {label}: {reason}")
        for attached in tuple(host.views):
            if attached.owner is peer:
                _retire(host.selector, attached.connection)
                host.views.remove(attached)
        _retire(host.selector, peer.connection)
        host.peers.remove(peer)
        if peer.slot is None:
            print(f"Multiplayer connection rejected: {reason}")
    elif view is not None:
        _retire(host.selector, view.connection)
        host.views.remove(view)
    else:
        _retire(host.selector, connection)


def _accept(host: _Host, now: float) -> None:
    for _ in range(4):
        try:
            sock, _ = host.listener.accept()
        except BlockingIOError:
            return
        pending = sum(peer.slot is None for peer in host.peers)
        if pending >= 4 or len(host.peers) + len(host.views) >= len(host.settings.slots) * 2 + 4:
            sock.close()
            continue
        sock.setblocking(False)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        connection = _Connection(
            sock,
            ServerProtocol(max_size=CONTROL_LIMIT),
            "handshake",
            now,
            now,
            None,
            [],
            bytearray(),
        )
        host.selector.register(sock, selectors.EVENT_READ, connection)
        host.peers.append(_RemotePeer(connection, None, -1, (now, 60.0), ""))


def _host_packet(
    stage: Stage, host: _Host, connection: _Connection, packet: Packet, now: float
) -> None:
    peer = next((p for p in host.peers if p.connection is connection), None)
    if isinstance(packet, Hello) and peer is not None and connection.phase == "hello":
        if (
            packet.version != VERSION
            or len(packet.code) > 128
            or not secrets.compare_digest(packet.code.encode(), host.connection_code.encode())
        ):
            raise NetworkError("Joining code or protocol version rejected")
        if packet.slot not in host.settings.slots:
            raise NetworkError("Requested player is not reserved for multiplayer")
        if any(p is not peer and p.slot == packet.slot for p in host.peers):
            raise NetworkError("Requested player is already connected")
        peer.slot, peer.session_key = packet.slot, secrets.token_urlsafe(24)
        _phase(connection, "neutral", now)
        _queue(
            connection,
            Welcome(
                VERSION,
                packet.slot,
                stage.gamepads[packet.slot].layout,
                peer.session_key,
                (stage.width, stage.height),
            ),
            now,
        )
    elif isinstance(packet, ViewHello) and peer is not None and connection.phase == "hello":
        if len(packet.session_key) > 128:
            raise NetworkError("View authorization rejected")
        owner = next(
            (
                p
                for p in host.peers
                if p.slot is not None
                and secrets.compare_digest(p.session_key.encode(), packet.session_key.encode())
            ),
            None,
        )
        if packet.version != VERSION or owner is None or any(v.owner is owner for v in host.views):
            raise NetworkError("View authorization rejected")
        host.peers.remove(peer)
        host.views.append(_ViewPeer(connection, owner, False, None))
        _phase(connection, "view", now)
    elif isinstance(packet, Input) and peer is not None and peer.slot is not None:
        if packet.sequence != peer.last_sequence + 1 or connection.phase not in (
            "neutral",
            "active",
        ):
            raise NetworkError("Input sequence or connection phase rejected")
        previous, available = peer.input_window
        available = min(60.0, available + max(0.0, now - previous) * 120)
        if available < 1:
            raise NetworkError("Input rate exceeded 120/s plus 60-sample burst allowance")
        peer.input_window = now, available - 1
        packet.sample.__post_init__()
        peer.last_sequence = packet.sequence
        if connection.phase == "neutral":
            if packet.sample != GamepadInput():
                raise NetworkError("Release controls before joining")
            _phase(connection, "view", now)
        else:
            suspended = bool(stage._pause_reasons - {"user"})
            _apply(stage.gamepads[peer.slot], GamepadInput() if suspended else packet.sample)
            _queue(connection, Accepted(packet.sequence), now)
    elif isinstance(packet, FrameRequest):
        view = next((v for v in host.views if v.connection is connection), None)
        if view is None or view.owner is None or view.requested:
            raise NetworkError("Unexpected frame request")
        if packet.after_sequence != view.last_sent_frame:
            raise NetworkError("Frame acknowledgement does not match displayed frame")
        view.sent_at = None
        view.requested = True
        if packet.after_sequence is not None and view.owner.connection.phase == "view":
            if view.owner.last_sequence != 0 or view.owner.slot is None:
                raise NetworkError("Neutral controls must precede activation")
            _phase(view.owner.connection, "active", now)
            _phase(connection, "active", now)
            stage._pending.append(RemoteChange(view.owner.slot, True, None))
            _queue(view.owner.connection, Accepted(0), now)
            print(f"Player {view.owner.slot + 1} connected with a live view")
    else:
        raise NetworkError("Unexpected multiplayer message")


def _client_packet(
    stage: Stage, client: _Client, connection: _Connection, packet: Packet, now: float
) -> None:
    if isinstance(packet, Welcome) and connection is client.control and connection.phase == "hello":
        if packet.version != VERSION or packet.slot != client.requested_slot:
            raise NetworkError("Host protocol or player assignment rejected")
        _size(packet.logical_size)
        stage.gamepads[0].layout = packet.layout
        client.session_key = packet.session_key
        sock = connection.socket
        assert sock is not None
        address = sock.getpeername()
        client.view = _connect(client.selector, str(address[0]), int(address[1]), view=True)
        _phase(connection, "neutral", now)
    elif isinstance(packet, Accepted) and connection is client.control:
        if not client.last_accepted < packet.sequence < client.next_input_sequence:
            raise NetworkError("Host acknowledged an invalid input sequence")
        client.last_accepted, client.last_acceptance_time = packet.sequence, now
        _phase(connection, "active", now)
    elif isinstance(packet, Frame) and connection is client.view:
        if packet.sequence < 0 or (
            client.frame_sequence is not None and packet.sequence <= client.frame_sequence
        ):
            raise NetworkError("Frame sequence did not advance")
        client.frame = _decode_frame(packet)
        client.frame_sequence, client.frame_received_at = packet.sequence, now
        if packet.paused:
            if not pygame.font.get_init():
                pygame.font.init()
            label = pygame.font.Font(None, 24).render("Host paused", True, "white", "black")
            client.frame.blit(label, (8, 8))
        _phase(connection, "frame_pending", now)
    else:
        raise NetworkError("Unexpected host message")


def _size(size: tuple[int, int]) -> None:
    if not 1 <= size[0] <= MAX_SIZE[0] or not 1 <= size[1] <= MAX_SIZE[1]:
        raise NetworkError("Unsupported frame dimensions; maximum is 1280x720")


def _decode_frame(packet: Frame) -> pygame.Surface:
    """Validate both declared and actual image bounds before creating a surface."""
    _size(packet.logical_size)
    if len(packet.png) > MAX_FRAME:
        raise NetworkError("Frame exceeded its encoded size limit")
    try:
        with Image.open(io.BytesIO(packet.png)) as picture:
            if picture.format != "PNG" or picture.size != packet.logical_size:
                raise NetworkError("Frame dimensions or format rejected")
            rgba = picture.convert("RGBA")
            return pygame.image.frombytes(rgba.tobytes(), rgba.size, "RGBA")
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        raise NetworkError("Invalid frame PNG; image could not be safely decoded") from error


def _events(stage: Stage, owner: _Host | _Client, connection: _Connection, now: float) -> None:
    events = connection.protocol.events_received()
    if len(events) > 256:
        raise NetworkError("Connection exceeded its per-read event budget")
    for event in events:
        if isinstance(event, Request) and isinstance(connection.protocol, ServerProtocol):
            if event.path != "/":
                raise NetworkError("Unknown WebSocket endpoint")
            connection.protocol.send_response(connection.protocol.accept(event))
            _phase(connection, "hello", now)
        elif isinstance(event, Response) and isinstance(owner, _Client):
            if connection.protocol.handshake_exc is not None:
                raise NetworkError("WebSocket handshake rejected")
            _phase(connection, "hello", now)
            packet: Packet = (
                Hello(VERSION, owner.connection_code, owner.requested_slot)
                if connection is owner.control
                else ViewHello(VERSION, owner.session_key)
            )
            _queue(connection, packet, now)
            if connection is owner.view:
                _queue(connection, FrameRequest(None), now)
                _phase(connection, "view", now)
        elif isinstance(event, WebFrame):
            if event.opcode == Opcode.CLOSE:
                closing = connection.protocol.close_rcvd
                if closing is not None and closing.code == 1000 and isinstance(owner, _Client):
                    print("The host ended the game.")
                    stage.stop()
                    return
                raise NetworkError(
                    closing.reason
                    if closing is not None and closing.reason
                    else "Peer closed the connection"
                )
            if event.opcode == Opcode.PONG:
                if connection.pending_ping is not None and event.data == connection.pending_ping[0]:
                    connection.pending_ping = None
                    connection.last_received = now
            elif event.opcode in (Opcode.BINARY, Opcode.CONT):
                connection.incoming_fragment.extend(event.data)
                view = isinstance(owner, _Client) and connection is owner.view
                limit = MAX_FRAME + CONTROL_LIMIT if view else CONTROL_LIMIT
                if len(connection.incoming_fragment) > limit:
                    raise NetworkError("Incoming message exceeded its size limit")
                if event.fin:
                    packet = decode(bytes(connection.incoming_fragment))
                    connection.incoming_fragment.clear()
                    connection.last_received = now
                    if isinstance(owner, _Host):
                        _host_packet(stage, owner, connection, packet, now)
                    else:
                        _client_packet(stage, owner, connection, packet, now)
            elif event.opcode != Opcode.PING:
                raise NetworkError("Only binary protocol messages are supported")
    _collect(connection, now)
    view_channel = (
        isinstance(owner, _Host) and any(view.connection is connection for view in owner.views)
    ) or (isinstance(owner, _Client) and connection is owner.view)
    if not view_channel and sum(len(data) for _, data in connection.outgoing) > 65536:
        raise NetworkError("Control connection buffer exceeded 64 KiB")


def _io(
    stage: Stage, owner: _Host | _Client, connection: _Connection, mask: int, now: float
) -> None:
    sock = connection.socket
    if sock is None:
        return
    if connection.phase == "connecting":
        failure = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        if failure:
            raise OSError(failure, "Connection failed")
        assert isinstance(connection.protocol, ClientProtocol)
        connection.protocol.send_request(connection.protocol.connect())
        _phase(connection, "handshake", now)
        _collect(connection, now)
    if mask & selectors.EVENT_READ:
        for _ in range(16):
            try:
                data = sock.recv(65536)
            except BlockingIOError:
                break
            if not data:
                raise NetworkError("Peer disconnected")
            connection.protocol.receive_data(data)
            _events(stage, owner, connection, now)
            if not stage.running:
                return
    if mask & selectors.EVENT_WRITE:
        _write(connection)


def _write(connection: _Connection) -> None:
    """Flush ready bytes without waiting or inserting a rendered-frame delay."""
    sock = connection.socket
    if sock is None:
        return
    for _ in range(64):
        if not connection.outgoing:
            return
        queued, remaining = connection.outgoing[0]
        try:
            sent = sock.send(remaining)
        except BlockingIOError:
            return
        if not sent:
            raise NetworkError("Socket made no write progress")
        if sent == len(remaining):
            connection.outgoing.pop(0)
        else:
            connection.outgoing[0] = queued, remaining[sent:]


def _connections(owner: _Host | _Client) -> tuple[_Connection, ...]:
    if isinstance(owner, _Host):
        return tuple([p.connection for p in owner.peers] + [v.connection for v in owner.views])
    return (owner.control,) if owner.view is None else (owner.control, owner.view)


def _health(connection: _Connection, now: float) -> None:
    if connection.socket is None:
        return
    if connection.outgoing and now - connection.outgoing[0][0] > 1:
        raise NetworkError("Connection is too slow; queued data is stale")
    if connection.phase in ("connecting", "handshake", "hello"):
        if now - connection.phase_started > 5:
            raise NetworkError("Connection or authorization timed out")
    elif connection.phase in ("neutral", "view") and now - connection.phase_started > 10:
        raise NetworkError("Release controls and wait for the first game view")
    if connection.pending_ping is not None:
        if now - connection.pending_ping[1] > 5:
            raise NetworkError("Heartbeat timed out")
    elif connection.phase not in ("connecting", "handshake") and now - connection.last_received > 1:
        nonce = secrets.token_bytes(8)
        connection.protocol.send_ping(nonce)
        connection.pending_ping = nonce, now
        _collect(connection, now)


def pump(stage: Stage, now: float) -> None:
    """Observe ready sockets and finite deadlines; never wait inside the engine."""
    owner = stage._network
    if owner is None:
        return
    for connection in _connections(owner):
        if connection.socket is not None:
            flags = selectors.EVENT_READ
            if connection.outgoing or connection.phase == "connecting":
                flags |= selectors.EVENT_WRITE
            owner.selector.modify(connection.socket, flags, connection)
    for key, mask in owner.selector.select(0):
        if isinstance(owner, _Host) and key.fileobj is owner.listener:
            _accept(owner, now)
            continue
        connection = key.data
        if not isinstance(connection, _Connection) or connection.socket is None:
            continue
        try:
            _io(stage, owner, connection, mask, now)
            if not stage.running:
                return
        except (
            OSError,
            NetworkError,
            msgspec.DecodeError,
            WebSocketException,
            ValueError,
        ) as error:
            if isinstance(owner, _Host):
                _lost(stage, owner, connection, str(error))
            else:
                raise NetworkError(f"Multiplayer session failed: {error}") from error
    if isinstance(owner, _Host):
        for view in tuple(owner.views):
            if view.sent_at is not None and now - view.sent_at > 1:
                _lost(
                    stage,
                    owner,
                    view.connection,
                    "Game view stalled; display acknowledgement timed out",
                )
    for connection in _connections(owner):
        try:
            _health(connection, now)
            _write(connection)
        except (OSError, NetworkError, WebSocketException) as error:
            if isinstance(owner, _Host):
                _lost(stage, owner, connection, str(error))
            else:
                raise
    if isinstance(owner, _Client):
        if owner.control.phase == "neutral" and _sample(stage.gamepads[0]) == GamepadInput():
            _queue(owner.control, Input(0, GamepadInput()), now)
            owner.next_input_sequence = 1
            _phase(owner.control, "view", now)
        elif owner.control.phase == "active":
            if now - owner.frame_received_at > 1 or now - owner.last_acceptance_time > 5:
                raise NetworkError("Game view or input acknowledgement is stale")
            _send_input(stage, owner, now)


def _send_input(stage: Stage, client: _Client, now: float) -> None:
    _queue(client.control, Input(client.next_input_sequence, _sample(stage.gamepads[0])), now)
    client.next_input_sequence += 1


def source_transition(slot: Gamepad) -> None:
    """Preserve rapid local button transitions before a final per-frame sample."""
    owner = slot._stage._network
    if isinstance(owner, _Client) and slot.index == 0 and owner.control.phase == "active":
        _send_input(slot._stage, owner, time.monotonic())


def capture(stage: Stage, now: float, *, presented: bool = False) -> None:
    owner = stage._network
    if isinstance(owner, _Client):
        if not presented:
            return
        if owner.view is not None and owner.view.phase == "frame_pending":
            _queue(owner.view, FrameRequest(owner.frame_sequence), now)
            _phase(owner.view, "active", now)
            _write(owner.view)
        return
    if presented:
        return
    if not isinstance(owner, _Host) or stage._target is None or now < owner.next_capture_at:
        return
    waiting = [
        view
        for view in owner.views
        if view.requested
        and view.owner is not None
        and view.owner.last_sequence >= 0
        and not view.connection.outgoing
    ]
    if not waiting:
        return
    target = stage._target
    picture = Image.frombytes("RGB", target.get_size(), pygame.image.tobytes(target, "RGB"))
    stream = io.BytesIO()
    picture.save(stream, format="PNG", compress_level=1)
    data = stream.getvalue()
    if len(data) > MAX_FRAME:
        raise NetworkError("Rendered image exceeds multiplayer frame limit")
    sequence = owner.next_frame_sequence
    packet = Frame(sequence, stage._tick, stage.paused, (stage.width, stage.height), data)
    for view in waiting:
        try:
            _queue(view.connection, packet, now)
            _write(view.connection)
            view.requested, view.last_sent_frame = False, sequence
            view.sent_at = now
        except (OSError, NetworkError, WebSocketException) as error:
            _lost(stage, owner, view.connection, str(error))
    owner.next_frame_sequence += 1
    owner.next_capture_at = now + 1 / 30


def overlay(stage: Stage) -> None:
    from .canvas import Canvas

    owner = stage._network
    if owner is None or stage._target is None:
        return
    canvas = Canvas(stage._target, stage)
    try:
        if isinstance(owner, _Host):
            labels = [
                f"P{index + 1}: {'connected' if remote_connected(stage.gamepads[index]) else 'waiting'}"
                for index in owner.settings.slots
            ]
            text = "  ".join(labels)
        else:
            text = f"Player {owner.requested_slot + 1}: {owner.control.phase} | audio on host"
        canvas.text(text, (-stage.width / 2 + 8, -stage.height / 2 + 24), size=16)
    finally:
        canvas._surface = None


def close(stage: Stage, *, failed: bool = False) -> None:
    owner, stage._network = stage._network, None
    if owner is None:
        return
    errors: list[BaseException] = []
    reason = (
        "Host game failed; see its traceback"
        if failed and isinstance(owner, _Host)
        else "Player session failed"
        if failed
        else "Session closed"
    )
    try:
        for connection in _connections(owner):
            try:
                _closing(connection, reason)
                _retire(owner.selector, connection)
            except BaseException as error:  # noqa: BLE001 -- retire independent sockets before re-raising
                errors.append(error)
        if isinstance(owner, _Host):
            owner.listener.close()
            owner.peers.clear()
            owner.views.clear()
        else:
            owner.frame = None
    finally:
        owner.selector.close()
    if errors:
        for secondary in errors[1:]:
            errors[0].add_note(f"Network cleanup also failed: {secondary!r}")
        raise errors[0]
