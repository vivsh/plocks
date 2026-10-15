"""Advanced: async functions compose with the same simulation-owned blocks."""

from PIL import Image

from plocks import Ease, Key, Script, Sprite, Stage

stage = Stage()
hero = Sprite(Image.new("RGBA", (32, 32), "orange"), y=-100)
stage.add(hero)


async def jump(actor: Sprite) -> None:
    await actor.glide_by(y=100, seconds=0.3, easing=Ease.OUT)
    await actor.glide_by(y=-100, seconds=0.3, easing=Ease.IN)


hero.on_key_down(Key.SPACE, Script(jump))
stage.run()
