"""Small positive example for inspecting completion and hover help in an editor."""

from PIL import Image

from plocks import Costumes, HumanJoint, Key, Skeleton, Sprite, Stage
from plocks.web.build import build

stage = Stage()
hero = Sprite(Image.new("RGBA", (16, 16)))
hero.move(10)
hero.x = 20
stage.add(hero)
hero.act(Costumes((hero.costume,), fps=5))
held = stage.keyboard.is_down(Key.RIGHT)
skeleton = Skeleton.human()
pose = skeleton.rest_pose().with_angles({HumanJoint.RIGHT_ELBOW: 60})
build_game = build

from plocks import Block, ClearBubble, During, GlideBy, Poses, Puppet, Say, Sequence, Think

spoken_walk: Block[Sprite] = Sequence(
    During(GlideBy(x=80, seconds=1), meanwhile=Say("Walking!", seconds=1)),
    Think("What next?"),
    ClearBubble(),
)
hero.say("Hello")
hero.clear_bubble()
stage.bubble_text_size = 28
person = Puppet.stick_figure()
puppet_dialogue: Block[Puppet] = Sequence(
    Say("Watch me"),
    Poses((person.pose,), fps=2),
    Think("Done", seconds=1),
)
