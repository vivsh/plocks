"""Explore three tile types, scene layers, camera movement and parallax."""

from pathlib import Path

from plocks import (
    Canvas,
    Key,
    MouseButton,
    Point,
    Sprite,
    SpriteSheet,
    Stage,
    TiledBackground,
    TileMap,
)

# Find the ready-made pictures next to main.py.
assets = Path(__file__).resolve().with_name("assets")
stage = Stage(width=800, height=450, background="#9bc7d2")
# Smaller layer numbers go behind bigger ones: sky, mountains, hills, then tiles.
clouds = TiledBackground(assets / "clouds.png", layer=-30, offset=(0, 0))
mountains = TiledBackground(assets / "mountains.png", layer=-20)
hills = TiledBackground(assets / "hills.png", layer=-10)
for background in (clouds, mountains, hills):
    stage.add(background)
# Each letter paints one tile. Dots leave empty space above the ground.
rows: list[str] = []
for _ in range(10):
    rows.append("." * 70)
rows.append("G" * 70)
rows.append("D" * 70)
rows.append("S" * 70)
world = TileMap(
    rows,
    {"G": assets / "grass.png", "D": assets / "dirt.png", "S": assets / "stone.png"},
    tile_size=(32, 32),
    x=-400,
    y=224,
    layer=0,
)
stage.add(world)
# A second tilemap puts plants in front of the hero, like scenery on a stage.
leaves = TileMap(
    ["F.....F........F......F...F........F....F....F.......F.....F..........F"],
    {"F": assets / "fern.png"},
    tile_size=(32, 64),
    x=-400,
    y=-60,
    layer=10,
)
stage.add(leaves)
# A spritesheet is several pictures in one file. Pick its first 32 × 40 frame.
sheet = SpriteSheet(assets / "hero_sheet.png", frame_size=(32, 40))
hero = Sprite(sheet.frame(row=0, column=0), x=-260, y=-76, layer=5)
stage.add(hero)
selected = "G"


# These @ lines connect functions to keys. selected remembers our paint choice.
@stage.on_key_down(Key.ONE)
def grass() -> None:
    # global means: change selected at the top of this file, not a new local variable.
    global selected
    selected = "G"


@stage.on_key_down(Key.TWO)
def dirt() -> None:
    global selected
    selected = "D"


@stage.on_key_down(Key.THREE)
def stone() -> None:
    global selected
    selected = "S"


@stage.on_click
def edit(position: Point, button: MouseButton) -> None:
    # The mouse gives a position in the window. Add the camera position
    # to find the same spot in our bigger world.
    cell = world.cell_at(x=position[0] + stage.camera[0], y=position[1] + stage.camera[1])
    if cell is not None:
        row, column = cell
        if button == MouseButton.RIGHT:
            world.set_tile(row=row, column=column, tile=None)
        else:
            world.set_tile(row=row, column=column, tile=selected)


# update runs each game step. Multiplying by dt makes speed mean pixels per second.
@stage.on_update
def update(dt: float) -> None:
    direction = 0
    if stage.keyboard.is_down(Key.RIGHT):
        direction += 1
    if stage.keyboard.is_down(Key.LEFT):
        direction -= 1
    hero.x = max(-360, min(1780, hero.x + direction * 220 * dt))
    stage.camera = (max(0, min(1440, hero.x)), 0)
    # Faraway scenery moves less than nearby scenery. This trick is called parallax.
    camera_x = stage.camera[0]
    clouds.offset = (-camera_x * 0.1, 0)
    mountains.offset = (-camera_x * 0.3, 0)
    hills.offset = (-camera_x * 0.6, 0)


@stage.on_draw
def draw(canvas: Canvas) -> None:
    canvas.text("SCROLLING WORLD", (-380, 207), size=29, color="#19384a")
    canvas.text(
        f"Camera x: {stage.camera[0]:.0f}    Paint: {selected}",
        (-380, 172),
        size=22,
        color="#19384a",
    )
    canvas.text(
        "Arrows: explore   1/2/3: tile   Click: paint   Right-click: erase",
        (-380, -198),
        size=18,
    )


if __name__ == "__main__":
    stage.run()
