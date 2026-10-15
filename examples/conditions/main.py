"""A named condition reads current held keys on each loop iteration."""

from PIL import Image

from plocks import If, Key, KeyDown, Loop, Move, Sprite, Stage

stage = Stage()
hero = Sprite(Image.new("RGBA", (24, 24), "orange"))
stage.add(hero)
hero.act(Loop(If(KeyDown(Key.RIGHT), then=Move(2))))
stage.run()
