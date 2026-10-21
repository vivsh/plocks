"""Let physics handle jumping, gravity and landing."""

from pathlib import Path

from plocks import (
    Anchor,
    Box,
    Event,
    GamepadButton,
    GamepadPress,
    Image,
    Sprite,
    Stage,
    TiledBackground,
    TileMap,
)

assets = Path(__file__).resolve().parent / "assets"
stage = Stage(width=800, height=450, physics=True, background="#fff0cc")

# Player one already has Space for jumping; map extra controls here.
player = stage.gamepads[0]
desert = Image(assets / "desert.png").resized(width=800, height=450)
scenery = TiledBackground(desert, layer=-10)
stage.add(scenery)
# A row of solid tiles is our floor. y is the TOP edge of a tile map.
sand = desert.cropped(x=0, y=418, width=32, height=32)
ground = TileMap(["G" * 27], {"G": sand}, tile_size=(32, 32), solid={"G"}, x=-432, y=-130)
stage.add(ground)
dino = Sprite(
    Image(assets / "dinosaur.png", anchor=Anchor.BOTTOM_CENTER).resized(72, 72),
    x=-260,
    y=-130,
)
stage.add(dino)
# The anchor is at the feet; the collision box reaches upward from there.
dino.body.shape = Box(38, 58, center=(6, 34))
dino.body.rotation_locked = True


@dino.on_button_down(GamepadButton.A, gamepad=player)
def jump(event: Event[Sprite, GamepadPress]) -> None:
    if event.target.body.grounded:
        event.target.body.impulse(y=460)


@stage.on_update
def scroll(event: Event[Stage, float]) -> None:
    x, y = scenery.offset
    scenery.offset = (x - 20 * event.data, y)


if __name__ == "__main__":
    stage.run()
