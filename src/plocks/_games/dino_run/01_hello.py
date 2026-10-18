"""Our first window: a dinosaur and a desert."""

from pathlib import Path

from plocks import BodyType, Costume, Sprite, Stage, TiledBackground

# __file__ means this Python file. Find its pictures even from another folder.
assets = Path(__file__).resolve().parent / "assets"
stage = Stage(width=800, height=450, background="#fff0cc")
scenery = TiledBackground(Costume(assets / "desert.png").resized(width=800, height=450))
stage.add(scenery)
dino = Sprite(
    Costume(assets / "dinosaur.png").resized(width=72, height=72),
    x=-260,
    y=-90,
    body_type=BodyType.NONE,
)
stage.add(dino)

# This opens the game only when we run this file, rather than import it.
if __name__ == "__main__":
    stage.run()
