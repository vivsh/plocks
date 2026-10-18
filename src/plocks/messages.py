"""Typed identity channels for broadcasts delivered through Event callbacks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

_D = TypeVar("_D")


@dataclass(frozen=True, slots=True, eq=False)
class Message(Generic[_D]):  # noqa: UP046 -- invariant payload prevents widening invalid sends
    """A stage-local identity channel, e.g. Message[int]("damage").

    Share this token between senders and receivers; equal names stay distinct.
    Use Message[None] when no payload is needed. Payloads are checked statically
    and passed by reference. Empty diagnostic names raise ValueError.
    """

    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("A message needs a nonempty diagnostic name")
