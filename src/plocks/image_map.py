"""Immutable named images from a JSON atlas or an ordinary typed loader."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from .imaging import Image, ImageSource, _image


@dataclass(frozen=True, init=False, eq=False, slots=True)
class ImageMap(Mapping[str, Image]):
    """Load named, differently sized images without a grid or playback state.

    metadata defaults to the source filename's sibling .json. Explicit relative
    paths use cwd. Built-in JSON Hash supports one atlas with unrotated, untrimmed
    rectangles. Unsupported packing raises AssetError with an export correction.

    A custom metadata(atlas) callable runs once and returns Mapping[str, Image].
    It may read any format. Its exceptions keep their traceback; the resulting
    mapping is copied and read-only. Sources and callbacks are not retained.
    Example: pictures = ImageMap("assets/actors.png"); hero = pictures["hero"].
    """

    _images: Mapping[str, Image]

    def __init__(
        self,
        source: ImageSource,
        *,
        metadata: str | Path | Callable[[Image], Mapping[str, Image]] | None = None,
    ) -> None:
        from ._image_map import _read, _snapshot

        atlas = _image(source)
        if callable(metadata):
            try:
                values = metadata(atlas)
            except Exception as error:
                error.add_note("While loading ImageMap with its custom metadata callable")
                raise
        else:
            if metadata is None:
                if not isinstance(source, (str, Path)):
                    raise ValueError(
                        "In-memory ImageMap sources need explicit metadata or a loader"
                    )
                path = Path(source).with_suffix(".json")
            else:
                path = Path(metadata)
            values = _read(atlas, path)
        object.__setattr__(self, "_images", MappingProxyType(_snapshot(values)))

    def __getitem__(self, name: str) -> Image:
        """Look up an exact exported name; unknown names raise KeyError."""
        return self._images[name]

    def __iter__(self) -> Iterator[str]:
        """Iterate exact image names in metadata/loader order."""
        return iter(self._images)

    def __len__(self) -> int:
        """Return the number of loaded named images."""
        return len(self._images)
