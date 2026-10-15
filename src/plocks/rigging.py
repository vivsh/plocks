"""Immutable pivot skeletons and complete parent-relative poses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from .geometry import Point, _number, _point, _rotate


class HumanJoint(StrEnum):
    """Discoverable pivot names used by Skeleton.human and Puppet.stick_figure."""

    ROOT = "root"
    SPINE = "spine"
    NECK = "neck"
    HEAD = "head"
    LEFT_SHOULDER = "left_shoulder"
    LEFT_ELBOW = "left_elbow"
    LEFT_HAND = "left_hand"
    RIGHT_SHOULDER = "right_shoulder"
    RIGHT_ELBOW = "right_elbow"
    RIGHT_HAND = "right_hand"
    LEFT_HIP = "left_hip"
    LEFT_KNEE = "left_knee"
    LEFT_FOOT = "left_foot"
    RIGHT_HIP = "right_hip"
    RIGHT_KNEE = "right_knee"
    RIGHT_FOOT = "right_foot"


@dataclass(frozen=True, slots=True)
class Joint:
    """Image pivot: parent-local offset in pixels and clockwise rest angle in degrees.

    A joint's own angle rotates its image and descendants, not its own offset.
    The single root has parent=None and offset=(0, 0).
    """

    parent: str | None
    offset: Point = (0.0, 0.0)
    angle: float = 0.0

    def __post_init__(self) -> None:
        if self.parent is not None and (
            not isinstance(self.parent, str) or not self.parent.strip()
        ):
            raise ValueError("Parent must be a nonempty name or None")
        object.__setattr__(self, "offset", _point(self.offset, "offset"))
        object.__setattr__(self, "angle", _number(self.angle, "angle") % 360)


@dataclass(frozen=True, slots=True, init=False, eq=False)
class Skeleton:
    """Immutable ordered pivot tree. Parents precede children; exactly one root is required."""

    _joints: Mapping[str, Joint]

    def __init__(self, joints: Mapping[str, Joint]) -> None:
        copied: dict[str, Joint] = {}
        roots = 0
        for name, joint in joints.items():
            if not isinstance(name, str) or not name.strip() or not isinstance(joint, Joint):
                raise ValueError("Skeleton entries require nonempty names and Joint values")
            if joint.parent is None:
                roots += 1
                if joint.offset != (0, 0):
                    raise ValueError("The root offset must be (0, 0)")
            elif joint.parent not in copied:
                raise ValueError(f"Parent {joint.parent!r} must precede {name!r}")
            copied[str(name)] = joint
        if roots != 1:
            raise ValueError("A skeleton requires exactly one root")
        object.__setattr__(self, "_joints", MappingProxyType(copied))

    @property
    def joints(self) -> Mapping[str, Joint]:
        """Read-only parent-before-child definitions."""
        return self._joints

    def rest_pose(self) -> Pose:
        """Create a complete pose from rest angles; no pose is cached."""
        return Pose(self, {name: joint.angle for name, joint in self.joints.items()})

    @staticmethod
    def human() -> Skeleton:
        """Upright human, with hip origin and named pivots; all rest angles are zero."""
        h = HumanJoint
        return Skeleton(
            {
                h.ROOT: Joint(None),
                h.SPINE: Joint(h.ROOT, (0, 40)),
                h.NECK: Joint(h.SPINE, (0, 10)),
                h.HEAD: Joint(h.NECK, (0, 12)),
                h.LEFT_SHOULDER: Joint(h.SPINE, (-16, 0)),
                h.LEFT_ELBOW: Joint(h.LEFT_SHOULDER, (0, -25)),
                h.LEFT_HAND: Joint(h.LEFT_ELBOW, (0, -24)),
                h.RIGHT_SHOULDER: Joint(h.SPINE, (16, 0)),
                h.RIGHT_ELBOW: Joint(h.RIGHT_SHOULDER, (0, -25)),
                h.RIGHT_HAND: Joint(h.RIGHT_ELBOW, (0, -24)),
                h.LEFT_HIP: Joint(h.ROOT, (-10, 0)),
                h.LEFT_KNEE: Joint(h.LEFT_HIP, (0, -35)),
                h.LEFT_FOOT: Joint(h.LEFT_KNEE, (0, -32)),
                h.RIGHT_HIP: Joint(h.ROOT, (10, 0)),
                h.RIGHT_KNEE: Joint(h.RIGHT_HIP, (0, -35)),
                h.RIGHT_FOOT: Joint(h.RIGHT_KNEE, (0, -32)),
            }
        )


@dataclass(frozen=True, slots=True, init=False, eq=False)
class Pose:
    """Complete immutable clockwise angles, bound to one exact skeleton instance."""

    _skeleton: Skeleton
    _angles: Mapping[str, float]

    def __init__(self, skeleton: Skeleton, angles: Mapping[str, float]) -> None:
        if angles.keys() != skeleton.joints.keys():
            raise ValueError("A pose must specify every joint, and no unknown joints")
        object.__setattr__(self, "_skeleton", skeleton)
        object.__setattr__(
            self,
            "_angles",
            MappingProxyType({name: _number(angles[name], name) % 360 for name in skeleton.joints}),
        )

    @property
    def skeleton(self) -> Skeleton:
        """The exact immutable topology for this pose."""
        return self._skeleton

    @property
    def angles(self) -> Mapping[str, float]:
        """Read-only parent-relative degrees normalized to [0, 360)."""
        return self._angles

    def with_angles(self, changes: Mapping[str, float]) -> Pose:
        """Create a complete pose replacing selected angles; unknown names raise KeyError."""
        for name in changes:
            if name not in self.angles:
                raise KeyError(name)
        return Pose(self.skeleton, {**self.angles, **changes})


def _pivots(pose: Pose) -> dict[str, tuple[Point, float]]:
    """Compute parent-local forward kinematics in operation-local storage."""
    result: dict[str, tuple[Point, float]] = {}
    for name, joint in pose.skeleton.joints.items():
        if joint.parent is None:
            result[name] = ((0.0, 0.0), pose.angles[name])
        else:
            (px, py), angle = result[joint.parent]
            dx, dy = _rotate(joint.offset, angle + 90)
            result[name] = ((px + dx, py + dy), angle + pose.angles[name])
    return result
