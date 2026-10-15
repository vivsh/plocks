"""Press Right to glide. Repeated presses wait until the current glide finishes."""

from PIL import Image

from plocks import GlideBy, Key, Sprite, Stage

stage = Stage()
cat = Sprite(Image.new("RGBA", (32, 32), "orange"))
stage.add(cat)
stage.on_key_down(Key.RIGHT, cat, GlideBy(x=60, seconds=0.4))
stage.run()
