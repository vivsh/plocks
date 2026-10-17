"""Positive typing fixture and small Pylance hover inspection surface."""

from PIL import Image

from plocks import (
    Action,
    Actor,
    BodyType,
    Box,
    Ease,
    Key,
    Message,
    MouseButton,
    Point,
    Puppet,
    Sprite,
    Stage,
)


def main() -> None:
    stage = Stage(physics=True)
    hero = Sprite(Image.new("RGBA", (16, 16)), body_type=BodyType.NONE)
    person = Puppet.stick_figure()
    stage.add(hero)
    stage.add(person)
    patrol = hero.repeat(10).glide_by(x=10, seconds=0.2).costumes((hero.costume,), fps=5)
    hero.on_start(patrol)
    left = hero.costume.flipped(horizontal=True)
    portrait = left.cropped(x=0, y=0, width=8, height=8)
    hero.costume = portrait.with_anchor(x=4, y=8).rotated(90).resized(width=16, height=16)

    @hero.on_key_down(Key.SPACE)
    def jump() -> Action:
        up = hero.glide_by(y=100, seconds=0.3, easing=Ease.OUT)
        return hero.glide_by(y=-100, seconds=0.3, easing=Ease.IN, after=up)

    steps = Message[int]("steps")

    @hero.on_message(steps)
    def walk(distance: int) -> Action:
        return hero.glide_by(x=distance, seconds=1)

    @person.on_click
    async def answer(position: Point, button: MouseButton) -> None:
        await person.say(f"Clicked {button.name} at {position}", seconds=1)

    @hero.on_update
    def move(dt: float) -> None:
        hero.x += 20 * dt

    person.body.shape = Box(20, 80)
    person.body.rotation_locked = True
    target: Actor = hero if stage.keyboard.is_down(Key.H) else person
    target.wait(0.2)
