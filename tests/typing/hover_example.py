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

from plocks import Message, Signal, WhenBusy

stage.add(person)
hero.on_start(spoken_walk)
person.on_start(puppet_dialogue)
hero.on_key_down(Key.SPACE, spoken_walk)
person.on_key_down(Key.P, puppet_dialogue, when_busy=WhenBusy.RESTART)
wave = Signal("wave")
person.on_message(wave, puppet_dialogue)
steps = Message[int]("steps")


def walk(distance: int) -> Block[Sprite]:
    return Sequence(GlideBy(x=distance, seconds=1), Say("Arrived"))


def pose_after_steps(distance: int) -> Block[Puppet]:
    return Sequence(GlideBy(x=distance, seconds=1), Poses((person.pose,), fps=2))


hero.on_message(steps, walk)
person.on_message(steps, pose_after_steps)

from plocks import Actor, MouseButton, Point


@hero.on_update
def move_hero(dt: float) -> None:
    hero.x += 20 * dt


@person.on_update
def turn_person(dt: float) -> None:
    person.turn_right(15 * dt)


@hero.on_click
def greet(position: Point, button: MouseButton) -> None:
    hero.say(f"Clicked at {position}")


@person.on_click
async def answer(position: Point, button: MouseButton) -> None:
    await stage.wait(0.1)
    person.say(button.name)


hero.on_click(spoken_walk)
person.on_click(puppet_dialogue)
target: Actor = hero if held else person
target.on_click(greet)
