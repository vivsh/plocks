"""Actionable library errors; exceptions from game callbacks remain unchanged."""

from __future__ import annotations


class PlocksError(Exception):
    """Base exception for a Plocks operation that cannot be completed."""


class AssetError(PlocksError):
    """An image, sound, or font cannot be read or decoded."""


class AudioError(PlocksError):
    """Audio cannot start, decode, or allocate a playback channel."""


class StageError(PlocksError):
    """A stage operation conflicts with its lifecycle or active native resources."""


class BuildError(PlocksError):
    """A project cannot be assembled into a portable browser website."""
