"""Moving image sprites; transforms own no synchronized rectangle state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._operations import _CostumeRun, _sample_costume
from ._scripts import _admit, _cancel, _conflicts
from .geometry import Bounds, Point, _integer, _number, _point, _positive, _rotate
from .imaging import Costume, CostumeSource, _costume
from .motion import Ease, RotationStyle, _mirrored, _visual_direction

if TYPE_CHECKING:
    from ._operations import _BubbleRun
    from .blocks import Block, Say, Think
    from .puppets import Puppet
    from .stage import Stage
    from .tiling import TileMap


class Sprite:
    """A movable image. Construct it, then add it with stage.add(sprite).

    Positions use logical pixels and the costume anchor. Movement is immediate
    and does not automatically stop at obstacles. Direction 90 faces right.
    """

    __slots__ = (
        "_bubble",
        "_direction",
        "_layer",
        "_rotation_style",
        "_scale",
        "_stage",
        "_visible",
        "_visual",
        "_x",
        "_y",
    )

    def __init__(
        self,
        source: CostumeSource,
        *,
        x: float = 0,
        y: float = 0,
        direction: float = 90,
        scale: float = 1,
        visible: bool = True,
        layer: int = 0,
    ) -> None:
        self._x = _number(x, "x")
        self._y = _number(y, "y")
        self._direction = _number(direction, "direction") % 360
        self._scale = _positive(scale, "scale")
        self._visible = visible
        self._layer = _integer(layer, "layer")
        self._visual: Costume | _CostumeRun = _costume(source)
        self._stage: Stage | None = None
        self._rotation_style = RotationStyle.ALL_AROUND
        self._bubble: Say | Think | _BubbleRun | None = None

    def say(self, text: str) -> None:
        """Show persistent speech; empty/whitespace clears it. Works while detached.

        Replaces the current bubble and cancels a timed bubble's entire root.
        Text is captured now, including f-strings. No timer or window is created.
        """
        from ._bubbles import _set_bubble
        from .blocks import Say

        _set_bubble(self, Say(text))

    def think(self, text: str) -> None:
        """Show persistent thought, replacing speech or thought; empty text clears.

        Like say(), this cancels a timed bubble's root and works while detached.
        Use Think(text, seconds=...) in a behavior for timed thought.
        """
        from ._bubbles import _set_bubble
        from .blocks import Think

        _set_bubble(self, Think(text))

    def clear_bubble(self) -> None:
        """Clear speech/thought, canceling any timed bubble's whole root behavior.

        Safe when already empty or detached. Synchronous callbacks can clear even
        while paused; a ClearBubble block waits for the next script phase.
        """
        from ._bubbles import _set_bubble

        _set_bubble(self, None)

    @property
    def x(self) -> float:
        """Anchor x in world pixels; increasing x moves right."""
        return self._x

    @x.setter
    def x(self, value: float) -> None:
        value = _number(value, "x")
        _conflicts(self, True, False)
        self._x = value

    @property
    def y(self) -> float:
        """Anchor y in world pixels; increasing y moves upward."""
        return self._y

    @y.setter
    def y(self, value: float) -> None:
        value = _number(value, "y")
        _conflicts(self, False, True)
        self._y = value

    @property
    def position(self) -> Point:
        """The same coordinates as (x, y), measured at the costume anchor."""
        return self._x, self._y

    @position.setter
    def position(self, value: Point) -> None:
        point = _point(value)
        _conflicts(self, True, True)
        self._x, self._y = point

    @property
    def direction(self) -> float:
        """Clockwise degrees from up: 0 up, 90 right, 180 down, 270 left."""
        return self._direction

    @direction.setter
    def direction(self, value: float) -> None:
        self._direction = _number(value, "direction") % 360

    @property
    def scale(self) -> float:
        """Positive uniform size multiplier; 1.0 is the source size."""
        return self._scale

    @scale.setter
    def scale(self, value: float) -> None:
        self._scale = _positive(value, "scale")

    @property
    def visible(self) -> bool:
        """Whether the sprite is drawn; collision queries still include it."""
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        self._visible = value

    @property
    def layer(self) -> int:
        """Drawing layer; higher numbers appear above lower numbers."""
        return self._layer

    @layer.setter
    def layer(self, value: int) -> None:
        self._layer = _integer(value, "layer")

    @property
    def costume(self) -> Costume:
        """The current immutable image; assigning it stops costume animation."""
        if isinstance(self._visual, _CostumeRun):
            assert self._stage is not None
            return _sample_costume(self._visual, self._stage.time)
        return self._visual

    @costume.setter
    def costume(self, value: CostumeSource) -> None:
        costume = _costume(value)
        _conflicts(self, False, False, visual=True)
        self._visual = costume

    @property
    def bounds(self) -> Bounds:
        """Derived world AABB, including transparent pixels and transformations."""
        costume = self.costume
        ax, ay = costume.anchor
        corners = [
            _rotate(
                (
                    -(cx - ax) if _mirrored(self.direction, self.rotation_style) else cx - ax,
                    ay - cy,
                ),
                _visual_direction(self.direction, self.rotation_style),
                self.scale,
            )
            for cx in (0, costume.width)
            for cy in (0, costume.height)
        ]
        return Bounds(
            self.x + min(p[0] for p in corners),
            self.y + min(p[1] for p in corners),
            self.x + max(p[0] for p in corners),
            self.y + max(p[1] for p in corners),
        )

    def move(self, steps: float) -> None:
        """Move immediately along direction. One step is one world pixel."""
        distance = _number(steps, "steps")
        dx, dy = _rotate((distance, 0), self.direction)
        self.position = self.x + dx, self.y + dy

    def move_to(self, *, x: float | None = None, y: float | None = None) -> None:
        """Place the anchor immediately at a world position; no collision response."""
        if x is None and y is None:
            raise ValueError("Supply x, y, or both")
        px = self.x if x is None else _number(x, "x")
        py = self.y if y is None else _number(y, "y")
        _conflicts(self, x is not None, y is not None)
        self._x, self._y = px, py

    def turn_left(self, degrees: float) -> None:
        """Turn counterclockwise in degrees; negative values turn the other way."""
        self.direction -= _number(degrees, "degrees")

    def turn_right(self, degrees: float) -> None:
        """Turn clockwise in degrees; negative values turn the other way."""
        self.direction += _number(degrees, "degrees")

    def touching(self, other: Sprite | Puppet | TileMap) -> bool:
        """Test AABB overlap, or solid tile overlap. Visibility does not affect it."""
        from .tiling import TileMap

        if isinstance(other, TileMap):
            return bool(other.tiles_touching(self.bounds, solid_only=True))
        return self.bounds.intersects(other.bounds)

    def act(self, block: Block[Sprite], *, restart: bool = False) -> None:
        """Schedule a reusable block; requires stage membership. Repeated act continues it."""
        from .errors import StageError

        stage = self._stage
        if stage is None:
            raise StageError("Add the actor to a stage before starting behavior")
        active = [root for root in stage._runs if root.actor is self and root.block is block]
        if active and not restart:
            return
        for root in active:
            _cancel(stage, root)
        _admit(stage, block.run(self), self, block)

    def stop(self, block: Block[Sprite] | None = None) -> None:
        """Cancel current behaviors, or only roots started from this exact block."""
        if self._stage is not None:
            for root in tuple(self._stage._runs):
                if root.actor is self and (block is None or root.block is block):
                    _cancel(self._stage, root)

    async def glide_by(
        self,
        *,
        x: float | None = None,
        y: float | None = None,
        seconds: float,
        easing: Ease = Ease.LINEAR,
    ) -> None:
        """Advanced: await relative motion in simulated seconds; omitted axes stay free."""
        from ._operations import _glide

        await _glide(self, x, y, seconds, easing, relative=True)

    async def glide_to(
        self,
        *,
        x: float | None = None,
        y: float | None = None,
        seconds: float,
        easing: Ease = Ease.LINEAR,
    ) -> None:
        """Advanced: await absolute world-coordinate motion in simulated seconds."""
        from ._operations import _glide

        await _glide(self, x, y, seconds, easing, relative=False)

    @property
    def rotation_style(self) -> RotationStyle:
        """Visual rotation only; movement always follows direction."""
        return self._rotation_style

    @rotation_style.setter
    def rotation_style(self, value: RotationStyle) -> None:
        if not isinstance(value, RotationStyle):
            raise TypeError("Use a RotationStyle value")
        self._rotation_style = value

    def point_towards(self, target: Point | Sprite | Puppet) -> None:
        """Immediately face a point or actor; coincident positions leave direction unchanged."""
        from math import atan2, degrees

        point = _point(target) if isinstance(target, tuple) else target.position
        dx, dy = point[0] - self.x, point[1] - self.y
        if dx or dy:
            self.direction = degrees(atan2(dx, dy))

    def go_to_random(self, bounds: Bounds | None = None) -> None:
        """Place the anchor uniformly inside bounds, defaulting to the visible world."""
        from random import uniform

        from .motion import _area

        area = _area(self, bounds)
        self.position = uniform(area.left, area.right), uniform(area.bottom, area.top)

    def bounce_on_edge(self, bounds: Bounds | None = None) -> bool:
        """Reflect outward movement and fit inside bounds; oversized actors raise ValueError."""
        from .motion import _bounce

        return _bounce(self, bounds)
