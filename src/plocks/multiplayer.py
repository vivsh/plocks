"""Explicit host configuration; constructing it opens no sockets."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address


@dataclass(frozen=True, slots=True)
class Multiplayer:
    """Share the game picture and reserve zero-based gamepad slots over LAN.

    (1,) reserves player two. The host owns gameplay and scores; joiners see
    its view with network delay. Audio remains on the host. Use trusted LANs
    or an independently arranged encrypted tunnel. Construction opens nothing.
    """

    slots: tuple[int, ...] = (1,)
    bind: str = "0.0.0.0"
    port: int = 8765

    def __post_init__(self) -> None:
        if not isinstance(self.slots, tuple) or not self.slots:
            raise ValueError("slots must be a nonempty tuple of zero-based gamepad indexes")
        if any(type(slot) is not int or slot < 0 for slot in self.slots):
            raise ValueError("Each remote slot must be a nonnegative integer")
        if len(set(self.slots)) != len(self.slots):
            raise ValueError("Remote slots must be unique")
        if not isinstance(self.bind, str):
            raise TypeError("bind must be a numeric IPv4 or IPv6 address")
        ip_address(self.bind)
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("port must be an integer in 1..65535")
