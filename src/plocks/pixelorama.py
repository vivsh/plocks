"""Pixelorama PNG/JSON exports become immutable frames and ordinary scripts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from types import MappingProxyType

from ._asset_json import _array, _document, _float, _int, _object, _text
from .errors import AssetError
from .geometry import Point
from .imaging import Costume
from .scripts import Script
from .sprites import Sprite


@dataclass(frozen=True, slots=True, init=False, eq=False)
class PixeloramaSheet:
    """Load a PNG and matching Pixelorama 1.2.2 JSON export, with authored timing.

    Export all frames, forward, merged visible layers, 100% size, no cropping,
    using ordinary rows/columns. metadata defaults to the PNG's sibling .json.
    Explicit paths resolve from cwd. Invalid/unsupported exports raise AssetError.
    The image and JSON must be exported together; same-sized stale pairs cannot
    be detected. Sources are snapshotted without creating a window.
    """

    _frames: tuple[Costume, ...]
    _durations: tuple[float, ...]
    _tags: Mapping[str, tuple[int, int]]

    def __init__(
        self, image: str | Path, *, metadata: str | Path | None = None, anchor: Point | None = None
    ) -> None:
        image_path = Path(image)
        metadata_path = image_path.with_suffix(".json") if metadata is None else Path(metadata)
        try:
            data = _document(metadata_path)
            durations, tags = _validate_export(data)
            width = _int(data.get("size_x"), "frame width", 1)
            height = _int(data.get("size_y"), "frame height", 1)
            columns, rows, orientation = _grid(data, len(durations))
            source = Costume(image_path)
            if image_path.suffix.lower() != ".png" or (source.width, source.height) != (
                width * columns,
                height * rows,
            ):
                raise AssetError("PNG dimensions do not match the exported rows/columns")
            frames: list[Costume] = []
            for index in range(len(durations)):
                column, row = (
                    divmod(index, rows) if orientation == 0 else (index % columns, index // columns)
                )
                frame = source.cropped(column * width, row * height, width, height)
                frames.append(
                    frame.with_anchor(*(anchor if anchor is not None else (width / 2, height / 2)))
                )
            object.__setattr__(self, "_frames", tuple(frames))
            object.__setattr__(self, "_durations", durations)
            object.__setattr__(self, "_tags", MappingProxyType(tags))
        except (ValueError, TypeError, AssetError) as error:
            raise AssetError(f"Cannot import Pixelorama export {metadata_path}: {error}") from error

    @property
    def frames(self) -> tuple[Costume, ...]:
        """Owned immutable costumes in original project order; zero-based indexing."""
        return self._frames

    @property
    def durations(self) -> tuple[float, ...]:
        """Per-frame hold times in simulation seconds, including the last frame."""
        return self._durations

    @property
    def animations(self) -> tuple[str, ...]:
        """Animation tag names in authored order; no playback state is stored."""
        return tuple(self._tags)

    def animation(self, name: str | None = None) -> Script[Sprite]:
        """Create a fresh editable Sprite script for a tag, or all frames if omitted.

        Unknown names raise KeyError. repeat() and later script edits affect only
        the returned Script. Shared scripts execute independently on each actor.
        """
        start, stop = (0, len(self.frames)) if name is None else self._tags[name]
        return Script(Sprite).costumes(
            self.frames[start:stop], durations=self.durations[start:stop]
        )


def _profile_int(profile: dict[str, object], key: str) -> int:
    value = profile.get(key)
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    raise AssetError(f"export_profile.{key} must be an exported integer setting")


def _validate_export(
    data: dict[str, object],
) -> tuple[tuple[float, ...], dict[str, tuple[int, int]]]:
    """Validate metadata independently of image selection, returning authored timing/tags."""
    if data.get("pixelorama_version") not in {"1.2.2", "v1.2.2", "v1.2.2-stable"}:
        raise AssetError("Use a tested Pixelorama 1.2.2 PNG + JSON export")
    profile = _object(data.get("export_profile"), "export_profile")
    expected = {
        "current_tab": 1,
        "file_format": 0,
        "frame_current_tag": 0,
        "direction": 0,
        "repeat_count": 0,
        "resize": 100,
        "crop_mode": 0,
        "export_layers": 0,
    }
    for key, value in expected.items():
        if _profile_int(profile, key) != value:
            raise AssetError(
                f"Unsupported export_profile.{key}; export all frames forward, merged visible layers, 100%, no crop"
            )
    for key in ("split_layers", "sheet_layers_as_separate_files", "erase_unselected_area"):
        if profile.get(key) != "false":
            raise AssetError(f"Unsupported export_profile.{key}; disable split layers/cropping")
    if _profile_int(profile, "orientation") not in (0, 1):
        raise AssetError("Use ordinary Rows or Columns, not tag-based packing")

    _int(data.get("size_x"), "frame width", 1)
    _int(data.get("size_y"), "frame height", 1)
    frames = _array(data.get("frames"), "frames")
    if not frames:
        raise AssetError("Pixelorama needs at least one frame")
    fps = _float(data.get("fps"), "fps", 0)
    if fps == 0:
        raise AssetError("fps must be positive")
    durations = tuple(
        _float(_object(frame, "frame").get("duration"), "frame duration", 0) / fps
        for frame in frames
    )
    if any(value <= 0 for value in durations):
        raise AssetError("Frame durations must be positive")
    _float(sum(durations), "total animation duration")
    _grid(data, len(frames))
    tags: dict[str, tuple[int, int]] = {}
    for raw in _array(data.get("tags", []), "tags"):
        tag = _object(raw, "tag")
        name = _text(tag.get("name"), "tag name")
        start = _int(tag.get("from"), "tag start", 1) - 1
        stop = _int(tag.get("to"), "tag end", 1)
        if name in tags or not 0 <= start < stop <= len(frames):
            raise AssetError(f"Duplicate or invalid animation tag {name!r}")
        tags[name] = (start, stop)
    return durations, tags


def _grid(data: dict[str, object], count: int) -> tuple[int, int, int]:
    """Derive packing dimensions/order; never retain export grid state on the asset."""
    profile = _object(data.get("export_profile"), "export_profile")
    lines = _profile_int(profile, "lines_count")
    if lines <= 0 or _profile_int(profile, "number_of_frames") != count:
        raise AssetError("Export frame count/line count does not match the project")
    orientation = _profile_int(profile, "orientation")
    columns, rows = (
        (ceil(count / lines), lines) if orientation == 0 else (lines, ceil(count / lines))
    )
    return columns, rows, orientation
