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


class ActionCancelled(PlocksError):
    """An advanced coroutine awaited an action that was canceled."""


class PhysicsError(PlocksError):
    """Physics is unavailable or a body operation conflicts with its role or lifetime."""
