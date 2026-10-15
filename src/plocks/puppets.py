"""Articulated image actors with immutable skeletons and one current pose."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, TypeVar, cast, overload

from ._operations import _PoseRun, _sample_pose
from ._scripts import WhenBusy, _admit, _cancel, _conflicts
from .geometry import Bounds, Color, Point, _integer, _number, _point, _positive, _rotate
from .imaging import Costume, CostumeSource, _costume
from .input import Key
from .messages import Message, Signal
from .motion import Ease, RotationStyle, _mirrored, _visual_direction
from .rigging import HumanJoint, Pose, Skeleton, _pivots

if TYPE_CHECKING:
    from ._operations import _BubbleRun
    from .blocks import Block, Say, Think
    from .sprites import Sprite
    from .stage import Stage
    from .tiling import TileMap


_D = TypeVar("_D")


class Puppet:
    """An articulated image actor. Construct it, then add it with stage.add(puppet).

    Positions use logical pixels and the costume anchor. Movement is immediate
    and does not automatically stop at obstacles. Direction 90 faces right.
    """

    __slots__ = (
        "_bubble",
        "_direction",
        "_layer",
        "_parts",
        "_pose",
        "_rotation_style",
        "_scale",
        "_skeleton",
        "_stage",
        "_visible",
        "_x",
        "_y",
    )

    def __init__(
        self, skeleton: Skeleton, *, parts: Mapping[str, CostumeSource], pose: Pose | None = None
    ) -> None:
        if not parts or any(name not in skeleton.joints for name in parts):
            raise ValueError("Supply at least one image part on existing joints")
        self._skeleton = skeleton
        self._parts = {name: _costume(source) for name, source in parts.items()}
        initial = skeleton.rest_pose() if pose is None else pose
        if initial.skeleton is not skeleton:
            raise ValueError("Pose belongs to another skeleton")
        self._pose: Pose | _PoseRun = initial
        self._x = self._y = 0.0
        self._direction = 90.0
        self._scale = 1.0
        self._visible = True
        self._layer = 0
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
    def skeleton(self) -> Skeleton:
        """Immutable topology; poses must reference this exact instance."""
        return self._skeleton

    @property
    def parts(self) -> Mapping[str, Costume]:
        """Read-only image attachments in painting order; keys remain fixed."""
        return MappingProxyType(self._parts)

    def set_part_costume(self, joint: str, costume: CostumeSource) -> None:
        """Replace an existing attachment without interrupting pose motion."""
        if joint not in self._parts:
            raise KeyError(joint)
        self._parts[joint] = _costume(costume)

    @staticmethod
    def stick_figure(*, color: Color = "white", stroke_width: float = 4.0) -> Puppet:
        """Create a human Puppet using generated capsule/disc costumes; no files needed."""
        return _stick_figure(color, stroke_width)

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
    def pose(self) -> Pose:
        """Current complete pose; assigning a pose cancels its active pose writer."""
        if isinstance(self._pose, _PoseRun):
            assert self._stage is not None
            return _sample_pose(self._pose, self._stage.time)
        return self._pose

    @pose.setter
    def pose(self, value: Pose) -> None:
        if value.skeleton is not self.skeleton:
            raise ValueError("Pose belongs to another skeleton")
        _conflicts(self, False, False, visual=True)
        self._pose = value

    @property
    def bounds(self) -> Bounds:
        """World AABB of all image corners, including transparent padding."""
        return _bounds(self, self.direction)

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

    def on_start(self, block: Block[Puppet]) -> None:
        """Run a block once when the game starts; register after add, before run.

        Detached actors or registration after startup raise StageError. The stage
        owns this binding; removal/re-addition does not replay startup.
        """
        from .errors import StageError

        if self._stage is None:
            raise StageError("Add the actor to a stage before registering events")
        self._stage.on_start(self, block)

    def on_key_down(
        self, key: Key, block: Block[Puppet], *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> None:
        """Bind a block to a new key press; attach this actor to a stage first.

        Keys are game-wide, not actor focus. Repeated triggers are ignored while
        this registration runs; RESTART cancels it and starts again. The stage
        owns the handler, skips it while detached, and clears it on closure.
        Detached registration raises StageError. Nothing runs inline.
        """
        from .errors import StageError

        if self._stage is None:
            raise StageError("Add the actor to a stage before registering events")
        self._stage.on_key_down(key, self, block, when_busy=when_busy)

    @overload
    def on_message(
        self, message: Signal, block: Block[Puppet], *, when_busy: WhenBusy = WhenBusy.IGNORE
    ) -> None: ...
    @overload
    def on_message(
        self,
        message: Message[_D],
        block: Callable[[_D], Block[Puppet]],
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None: ...
    def on_message(
        self,
        message: Signal | Message[_D],
        block: Block[Puppet] | Callable[[_D], Block[Puppet]],
        *,
        when_busy: WhenBusy = WhenBusy.IGNORE,
    ) -> None:
        """Bind a signal block or typed payload-to-block factory; attach first.

        Example: hero.on_message(hit, recoil), where recoil accepts hit's payload
        and returns a compatible block. Factories run only for accepted deliveries
        when execution starts. Busy triggers default to IGNORE; RESTART cancels
        and replaces the invocation. Registrations belong to the current stage,
        stay inactive while detached, and never transfer to another stage.
        Detached registration raises StageError. Nothing runs inline.
        """
        from .errors import StageError

        if self._stage is None:
            raise StageError("Add the actor to a stage before registering events")
        if isinstance(message, Signal):
            self._stage.on_message(message, self, cast("Block[Puppet]", block), when_busy=when_busy)
        else:
            self._stage.on_message(
                message, self, cast("Callable[[_D], Block[Puppet]]", block), when_busy=when_busy
            )

    def act(self, block: Block[Puppet], *, restart: bool = False) -> None:
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

    def stop(self, block: Block[Puppet] | None = None) -> None:
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


def _bounds(actor: Puppet, direction: float) -> Bounds:
    points: list[Point] = []
    pivots = _pivots(actor.pose)
    for name, costume in actor._parts.items():
        (px, py), angle = pivots[name]
        ax, ay = costume.anchor
        for x in (0, costume.width):
            for y in (0, costume.height):
                dx, dy = _rotate((x - ax, ay - y), angle + 90)
                local = (px + dx, py + dy)
                if _mirrored(direction, actor.rotation_style):
                    local = (-local[0], local[1])
                dx, dy = _rotate(
                    local, _visual_direction(direction, actor.rotation_style), actor.scale
                )
                points.append((actor.x + dx, actor.y + dy))
    return Bounds(
        min(p[0] for p in points),
        min(p[1] for p in points),
        max(p[0] for p in points),
        max(p[1] for p in points),
    )


def _stick_figure(color: Color, stroke_width: float) -> Puppet:
    from math import ceil, floor

    import pygame
    from PIL import Image, ImageDraw

    width = _positive(stroke_width, "stroke_width")
    rgba = tuple(pygame.Color(color))
    skeleton = Skeleton.human()
    parts: dict[str, CostumeSource] = {}
    for name in skeleton.joints:
        ends = [joint.offset for joint in skeleton.joints.values() if joint.parent == name]
        radius = 10.0 if name == HumanJoint.HEAD else width / 2
        if not ends and name != HumanJoint.HEAD:
            continue
        points = [(0.0, 0.0), *ends]
        left = floor(min(x for x, _ in points) - radius)
        top = ceil(max(y for _, y in points) + radius)
        right = ceil(max(x for x, _ in points) + radius)
        bottom = floor(min(y for _, y in points) - radius)
        image = Image.new("RGBA", (max(1, right - left + 1), max(1, top - bottom + 1)))
        draw = ImageDraw.Draw(image)
        for x, y in ends:
            draw.line([(-left, top), (x - left, top - y)], fill=rgba, width=max(1, round(width)))
        for x, y in points:
            r = radius if name == HumanJoint.HEAD else width / 2
            draw.ellipse((x - left - r, top - y - r, x - left + r, top - y + r), fill=rgba)
        parts[name] = Costume(image, anchor=(-left, top))
    return Puppet(skeleton, parts=parts)
