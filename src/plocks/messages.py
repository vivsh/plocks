"""Identity-based, stage-local channels; names label channels, not lookup keys."""

from dataclasses import dataclass
from typing import Generic, TypeVar

Payload = TypeVar("Payload")


@dataclass(frozen=True, slots=True, eq=False)
class Signal:
    """A payload-free event token. Share the same instance between senders and receivers."""

    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("A signal needs a nonempty diagnostic name")


@dataclass(frozen=True, slots=True, eq=False)
class Message(Generic[Payload]):  # noqa: UP046 -- invariant payload prevents unsafe widening
    """An invariant typed payload channel, for example Message[int]('score added')."""

    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("A message needs a nonempty diagnostic name")
