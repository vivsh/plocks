"""Immutable images, image frames, human poses and a tiny image-part rig."""

from pathlib import Path

from plocks import HumanJoint, Image, Joint, Puppet, Skeleton, Sprite, Stage

assets = Path(__file__).resolve().parents[1] / "assets"
stage = Stage(width=800, height=450, background="#24384b")
idle = Image(assets / "dinosaur.png").resized(width=72, height=72)
# Transforming an Image makes another image; idle is still unchanged.
hero = Sprite(idle, x=-260)
stage.add(hero)
flip = idle.flipped(horizontal=True)
hero.on_start(hero.repeat().images((idle, flip), fps=2))

person = Puppet.stick_figure(color="#fff0cc", stroke_width=4)
person.x = -40
stage.add(person)
rest = person.skeleton.rest_pose()
wave = rest.with_angles({HumanJoint.RIGHT_ELBOW: 60})
person.on_start(person.repeat().poses((rest, wave, rest), fps=2))

# Each image anchor sits on its named joint. Child parts follow their parent.
skeleton = Skeleton({"body": Joint(parent=None), "badge": Joint(parent="body", offset=(25, 10))})
rig = Puppet(
    skeleton,
    parts={"body": idle, "badge": Image(assets / "coin.png").resized(width=24, height=24)},
)
rig.x = 220
stage.add(rig)
base = skeleton.rest_pose()
turn = base.with_angles({"body": 35})
rig.on_start(rig.repeat().poses((base, turn, base), fps=1))

if __name__ == "__main__":
    stage.run()
