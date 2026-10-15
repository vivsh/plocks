"""Immutable OGG assets and independent, stage-owned playback occurrences."""

from __future__ import annotations

import io
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pygame

from .errors import AssetError, AudioError
from .geometry import _number


@dataclass(frozen=True, init=False, eq=False)
class Sound:
    """An OGG/Vorbis file snapshot; play it with stage.play(sound).

    Constructing a sound opens no audio device. Missing or non-Vorbis assets
    raise AssetError. Each playback decodes its own independent sample.
    """

    _encoded: bytes
    _name: str

    def __init__(self, path: str | Path) -> None:
        filename = Path(path)
        try:
            data = filename.read_bytes()
        except OSError as error:
            raise AssetError(f"Cannot read sound {filename}: {error}") from error
        if (
            filename.suffix.lower() != ".ogg"
            or not data.startswith(b"OggS")
            or b"\x01vorbis" not in data[:4096]
        ):
            raise AssetError(f"Use an OGG/Vorbis sound: {filename}")
        object.__setattr__(self, "_encoded", data)
        object.__setattr__(self, "_name", str(filename))


class Voice:
    """One sound occurrence. A finished handle cannot affect a reused channel."""

    __slots__ = ("_channel", "_sample")

    def __init__(self) -> None:
        """Create a finished handle; obtain an active occurrence through Stage.play."""
        self._sample: pygame.mixer.Sound | None = None
        self._channel: pygame.mixer.Channel | None = None

    @property
    def finished(self) -> bool:
        """True after completion or stop. A paused occurrence is not finished."""
        if self._channel is not None and not self._channel.get_busy():
            self.stop()
        return self._channel is None

    def stop(self) -> None:
        """Stop only this occurrence. Safe to call again after retirement."""
        if self._channel is not None:
            self._channel.stop()
        self._channel = None
        self._sample = None


def _volume(value: float) -> float:
    result = _number(value, "volume", minimum=0)
    if result > 1:
        raise ValueError("volume must be between 0 and 1")
    return result


def _play(sound: Sound, volume: float, loop: bool) -> Voice:
    """Allocate without stealing. Stage retires old handles before this call."""
    try:
        if pygame.mixer.get_init() is None:
            pygame.mixer.init(frequency=44100, size=-16, channels=2)
            pygame.mixer.set_num_channels(16)
        channel = pygame.mixer.find_channel()
        if channel is None:
            raise AudioError("All 16 voices are busy; stop an occurrence before playing another")
        if sys.platform == "emscripten":
            # SDL's wasm reader requires a filesystem path, not Python file objects.
            with tempfile.TemporaryDirectory(prefix="plocks-sound-") as directory:
                path = Path(directory) / "sound.ogg"
                path.write_bytes(sound._encoded)
                sample = pygame.mixer.Sound(str(path))
        else:
            sample = pygame.mixer.Sound(file=io.BytesIO(sound._encoded))
        sample.set_volume(volume)
        channel.play(sample, loops=-1 if loop else 0)
        voice = Voice()
        voice._sample = sample
        voice._channel = channel
        return voice
    except (pygame.error, RuntimeError) as error:
        raise AudioError(f"Cannot play {sound._name}: {error}") from error
