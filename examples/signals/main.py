"""Press Space: a message makes another actor dance."""

from PIL import Image

from plocks import Broadcast, GlideBy, Key, Sequence, Signal, Sprite, Stage

stage = Stage()
hero = Sprite(Image.new("RGBA", (24, 24), "orange"), x=-80)
friend = Sprite(Image.new("RGBA", (24, 24), "skyblue"), x=80)
stage.add(hero)
stage.add(friend)
dance = Signal("dance")
stage.on_key_down(Key.SPACE, hero, Broadcast(dance))
stage.on_message(dance, friend, Sequence(GlideBy(y=60, seconds=0.3), GlideBy(y=-60, seconds=0.3)))
stage.run()
