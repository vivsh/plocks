"""A typed payload factory turns received data into ordinary blocks."""

from dataclasses import dataclass

from PIL import Image

from plocks import Block, Broadcast, GlideBy, Key, Message, Sequence, Sprite, Stage


@dataclass(frozen=True)
class Hit:
    push: float


stage = Stage()
hero = Sprite(Image.new("RGBA", (24, 24), "orange"), x=-80)
enemy = Sprite(Image.new("RGBA", (24, 24), "skyblue"), x=80)
stage.add(hero)
stage.add(enemy)
hit = Message[Hit]("hit")


def recoil(data: Hit) -> Block[Sprite]:
    return Sequence(GlideBy(x=data.push, seconds=0.1), GlideBy(x=-data.push, seconds=0.2))


enemy.on_message(hit, recoil)
hero.on_key_down(Key.H, Broadcast(hit, Hit(push=20)))
stage.run()
