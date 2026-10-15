"""Puppet pivot geometry, immutable complete poses, and shared block sampling."""

import pytest
from PIL import Image

from plocks import (
    Costume,
    HumanJoint,
    Joint,
    Pose,
    Poses,
    Puppet,
    RotationStyle,
    Skeleton,
    Stage,
)
from plocks._runtime import close
from plocks._scripts import _sample, _step
from plocks.rigging import _pivots


def rig() -> Skeleton:
    """A child pivot ten pixels above its root distinguishes pivot from endpoint semantics."""
    return Skeleton({"root": Joint(None), "hand": Joint("root", (0, 10))})


def puppet(skeleton: Skeleton) -> Puppet:
    """Attach an asymmetric image to the hand pivot."""
    return Puppet(
        skeleton, parts={"hand": Costume(Image.new("RGBA", (4, 8), "red"), anchor=(2, 0))}
    )


def test_pivot_own_angle_does_not_move_pivot() -> None:
    """Own rotation moves the image around its pivot; parent rotation moves child pivots."""
    skeleton = rig()
    pose = skeleton.rest_pose()
    assert _pivots(pose)["hand"][0] == (0, 10)
    bent = pose.with_angles({"hand": 90})
    assert _pivots(bent)["hand"][0] == (0, 10)
    assert _pivots(pose.with_angles({"root": 90}))["hand"][0] == (10, 0)
    actor = puppet(skeleton)
    actor.pose = bent
    assert actor.bounds.left == pytest.approx(-8)
    assert actor.bounds.top == pytest.approx(12)
    actor.rotation_style = RotationStyle.LEFT_RIGHT
    actor.direction = 270
    assert actor.bounds.right == pytest.approx(8)


def test_pose_sampling_and_freeze() -> None:
    """Shortest angles cross zero, half turns go clockwise, and removal freezes a complete pose."""
    skeleton = rig()
    actor = puppet(skeleton)
    stage = Stage()
    stage.add(actor)
    stage._state = "running"
    try:
        start = skeleton.rest_pose().with_angles({"hand": 350})
        end = start.with_angles({"hand": 10})
        actor.act(Poses((start, end), fps=1))
        _step(stage)
        stage._tick = 30
        _sample(stage)
        _step(stage)
        assert actor.pose.angles["hand"] == pytest.approx(0)
        stage.remove(actor)
        frozen = actor.pose
        stage.add(actor)
        stage._tick = 90
        _step(stage)
        assert actor.pose is frozen
        rest = skeleton.rest_pose()
        half = rest.with_angles({"hand": 180})
        actor.act(Poses((rest, half), fps=1))
        _step(stage)
        stage._tick += 30
        _step(stage)
        assert actor.pose.angles["hand"] == pytest.approx(90)
    finally:
        close(stage)


def test_validation_snapshot_and_part_replacement() -> None:
    """Topology/pose invariants fail early and part replacements preserve pose ownership."""
    skeleton = rig()
    angles = {"root": 0.0, "hand": 10.0}
    pose = Pose(skeleton, angles)
    angles["hand"] = 99
    assert pose.angles["hand"] == 10
    with pytest.raises(ValueError):
        Pose(skeleton, {"root": 0})
    with pytest.raises(KeyError):
        pose.with_angles({"typo": 0})
    with pytest.raises(ValueError):
        Poses((pose, rig().rest_pose()), fps=1)
    with pytest.raises(ValueError):
        Puppet(rig(), parts={"hand": Image.new("RGBA", (2, 2))}, pose=pose)
    actor = puppet(skeleton)
    actor.pose = pose
    actor.set_part_costume("hand", Image.new("RGBA", (3, 3), "blue"))
    assert actor.pose is pose and actor.parts["hand"].width == 3
    with pytest.raises(KeyError):
        actor.set_part_costume("root", actor.parts["hand"])


@pytest.mark.parametrize(
    "joints",
    [
        {},
        {"root": Joint(None, (1, 0))},
        {"child": Joint("missing")},
        {"one": Joint(None), "two": Joint(None)},
        {"root": Joint(None), "child": Joint("child")},
    ],
)
def test_invalid_topologies(joints: dict[str, Joint]) -> None:
    """Root placement, ordering, and cycles are validated before rendering."""
    with pytest.raises(ValueError):
        Skeleton(joints)


def test_stick_preset_uses_image_parts() -> None:
    """The preset is an ordinary Puppet with generated immutable costumes."""
    actor = Puppet.stick_figure()
    assert isinstance(actor, Puppet) and actor.parts
    assert actor.skeleton.joints[HumanJoint.RIGHT_ELBOW].offset == (0, -25)
    assert actor.bounds.top >= 72
    actor.pose = actor.pose.with_angles({HumanJoint.RIGHT_ELBOW: 60})
    assert actor.bounds.width > 0
