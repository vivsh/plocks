"""Closed multiplayer wire records, imported only when networking is requested."""

from __future__ import annotations

from typing import cast

import msgspec

from .gamepads import GamepadInput, GamepadLayout

VERSION = 1
MAX_FRAME = 4 * 1024 * 1024
MAX_SIZE = (1280, 720)
CONTROL_LIMIT = 4096


class Hello(msgspec.Struct, tag=True, frozen=True, forbid_unknown_fields=True):
    version: int
    code: str
    slot: int


class Welcome(msgspec.Struct, tag=True, frozen=True, forbid_unknown_fields=True):
    version: int
    slot: int
    layout: GamepadLayout
    session_key: str
    logical_size: tuple[int, int]


class Input(msgspec.Struct, tag=True, frozen=True, forbid_unknown_fields=True):
    sequence: int
    sample: GamepadInput


class Accepted(msgspec.Struct, tag=True, frozen=True, forbid_unknown_fields=True):
    sequence: int


class ViewHello(msgspec.Struct, tag=True, frozen=True, forbid_unknown_fields=True):
    version: int
    session_key: str


class FrameRequest(msgspec.Struct, tag=True, frozen=True, forbid_unknown_fields=True):
    after_sequence: int | None


class Frame(msgspec.Struct, tag=True, frozen=True, forbid_unknown_fields=True):
    sequence: int
    tick: int
    paused: bool
    logical_size: tuple[int, int]
    png: bytes


type Packet = Hello | Welcome | Input | Accepted | ViewHello | FrameRequest | Frame


def decode(data: bytes) -> Packet:
    """Decode a closed tagged variant; input ranges remain explicit validation."""
    return cast(Packet, msgspec.msgpack.decode(data, type=Packet))


def encode(packet: Packet) -> bytes:
    return msgspec.msgpack.encode(packet)
