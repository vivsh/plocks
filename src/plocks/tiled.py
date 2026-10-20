"""Tiled JSON exports load into ordinary editable TileMaps and authored markers."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from ._asset_json import _array, _bool, _document, _float, _int
from ._tiled import _color, _flatten, _markers, _tile_layer, _tilesets
from .errors import AssetError
from .geometry import Bounds, Color, Point, _integer, _number
from .imaging import Image
from .tiling import TileMap


class TiledMap:
    """Import a finite orthogonal JSON map without opening a window or adding objects.

    x/y place the map's top-left in world coordinates. layers contains editable
    TileMaps; points and regions are authored world coordinates, not live parents.
    Unsupported export features raise AssetError instead of changing the artwork.
    """

    __slots__ = ("_background", "_layers", "_points", "_regions")

    def __init__(self, path: str | Path, *, x: float = 0, y: float = 0, layer: int = 0) -> None:
        path = Path(path)
        x, y, layer = _number(x, "x"), _number(y, "y"), _integer(layer, "layer")
        try:
            data = _document(path)
            if (
                data.get("orientation") != "orthogonal"
                or _bool(data.get("infinite", False), "infinite")
                or data.get("renderorder", "right-down") != "right-down"
            ):
                raise AssetError("Use a finite orthogonal right-down Tiled JSON map")
            width, height = (
                _int(data.get("width"), "width", 1),
                _int(data.get("height"), "height", 1),
            )
            size = (
                _int(data.get("tilewidth"), "tilewidth", 1),
                _int(data.get("tileheight"), "tileheight", 1),
            )
            palette, overrides = _tilesets(path, _array(data.get("tilesets"), "tilesets"), size)
            layers: dict[str, TileMap] = {}
            points: dict[str, Point] = {}
            regions: dict[str, Bounds] = {}
            variants: dict[str, Image] = {}
            origin = (
                x + _float(data.get("parallaxoriginx", 0), "parallax origin x"),
                y - _float(data.get("parallaxoriginy", 0), "parallax origin y"),
            )
            for name, item in _flatten(_array(data.get("layers"), "layers")):
                try:
                    position = (
                        x + _float(item.get("offsetx", 0), "offset x"),
                        y - _float(item.get("offsety", 0), "offset y"),
                    )
                    if item.get("type") == "tilelayer":
                        if name in layers:
                            raise AssetError("Duplicate qualified layer name")
                        layers[name] = _tile_layer(
                            item,
                            palette,
                            overrides,
                            variants,
                            (width, height),
                            size,
                            position,
                            origin,
                            layer + len(layers),
                        )
                    elif item.get("type") == "objectgroup":
                        _markers(name, item, position, points, regions)
                    else:
                        raise AssetError(
                            "Only tile layers, groups and point/rectangle object layers are supported"
                        )
                except (AssetError, ValueError, TypeError, KeyError) as error:
                    raise AssetError(f"Layer {name}: {error}") from error
            if not layers:
                raise AssetError("At least one tile layer is required")
            self._layers: Mapping[str, TileMap] = MappingProxyType(layers)
            self._points: Mapping[str, Point] = MappingProxyType(points)
            self._regions: Mapping[str, Bounds] = MappingProxyType(regions)
            self._background = (
                _color(data["backgroundcolor"]) if "backgroundcolor" in data else None
            )
        except (AssetError, ValueError, TypeError, KeyError) as error:
            raise AssetError(f"Cannot import Tiled map {path}: {error}") from error

    @property
    def layers(self) -> Mapping[str, TileMap]:
        """TileMaps in authored painting order; add each to a Stage explicitly."""
        return self._layers

    @property
    def points(self) -> Mapping[str, Point]:
        """Named spawn/waypoint positions with qualified layer/name keys."""
        return self._points

    @property
    def regions(self) -> Mapping[str, Bounds]:
        """Named authored rectangles in world coordinates, not automatic colliders."""
        return self._regions

    @property
    def background(self) -> Color | None:
        """Optional authored color; loading never changes a Stage implicitly."""
        return self._background

    @property
    def bounds(self) -> Bounds:
        """Union of the current imported layers' world bounds, derived on access."""
        bounds = tuple(layer.bounds for layer in self.layers.values())
        return Bounds(
            min(b.left for b in bounds),
            min(b.bottom for b in bounds),
            max(b.right for b in bounds),
            max(b.top for b in bounds),
        )
