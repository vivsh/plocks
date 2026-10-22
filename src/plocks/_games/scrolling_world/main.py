"""Explore three tile types, scene layers, camera movement and parallax."""

from pathlib import Path

from plocks import (
    Anchor,
    Bounds,
    Click,
    Event,
    GamepadButton,
    GamepadPress,
    ImageGrid,
    Key,
    Label,
    MouseButton,
    Panel,
    Sprite,
    Stage,
    TileMap,
)

# Find assets beside this script, even when running from another folder.
assets = Path(__file__).resolve().parent / "assets"
stage = Stage(width=800, height=450, background="#9bc7d2")

# Add this game's controls to player one.
player = stage.gamepads[0]
player.map_left_stick(left=Key.LEFT, right=Key.RIGHT)
player.map_key(Key.ONE, GamepadButton.L)
player.map_key(Key.THREE, GamepadButton.X)
player.map_key(Key.TWO, GamepadButton.R)
# Smaller layers go behind. Distant scenery scrolls less: this is parallax.
for picture, layer, factor in (("clouds", -30, 0.1), ("mountains", -20, 0.3), ("hills", -10, 0.6)):
    background = TileMap(
        ["BBBB"],
        {"B": assets / f"{picture}.png"},
        tile_size=(512, 450),
        x=-400,
        y=225,
        layer=layer,
        parallax=(factor, 0),
    )
    stage.add(background)
# Each letter paints one tile. Dots leave empty space above the ground.
rows = ["." * 70] * 10 + ["G" * 70, "D" * 70, "S" * 70]
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
# An image grid holds equal-sized pictures. Pick its first 32 × 40 frame.
sheet = ImageGrid(assets / "hero_sheet.png", frame_size=(32, 40))
hero = Sprite(sheet.frame(row=0, column=0), x=-260, y=-76, layer=5)
stage.add(hero)
# A one-window-tall rectangle keeps the view scrolling sideways only.
stage.follow(hero, bounds=Bounds(world.bounds.left, -225, world.bounds.right, 225))
selected = "G"


hud = Panel(position=(0, 185), width=800, height=80, color="#19384a")
hud.add(Label("SCROLLING WORLD", position=(-380, 18), anchor=Anchor.CENTER_LEFT, size=29))
status = Label("Camera x: 0    Paint: G", position=(-380, -17), anchor=Anchor.CENTER_LEFT, size=22)
hud.add(status)
stage.add(hud)
help_bar = Panel(position=(0, -205), width=800, height=40)
help_bar.add(Label("Arrows: explore   1/2/3: tile   Click: paint   Right-click: erase", size=18))
stage.add(help_bar)


# These @ lines connect functions to keys. selected remembers our paint choice.
@stage.on_button_down(GamepadButton.L, gamepad=player)
def grass(event: Event[Stage, GamepadPress]) -> None:
    # global means: change selected at the top of this file, not a new local variable.
    global selected
    selected = "G"


@stage.on_button_down(GamepadButton.R, gamepad=player)
def dirt(event: Event[Stage, GamepadPress]) -> None:
    global selected
    selected = "D"


@stage.on_button_down(GamepadButton.X, gamepad=player)
def stone(event: Event[Stage, GamepadPress]) -> None:
    global selected
    selected = "S"


@stage.on_click
def edit(event: Event[Stage, Click]) -> None:
    # The mouse gives a position in the window. Add the camera position
    # to find the same spot in our bigger world.
    position, button = event.data
    # The screen panels are instructions, not paintable parts of our world.
    if position[1] > 145 or position[1] < -185:
        return
    cell = world.cell_at(x=position[0] + stage.camera[0], y=position[1] + stage.camera[1])
    if cell is not None:
        row, column = cell
        if button == MouseButton.RIGHT:
            world.set_tile(row=row, column=column, tile=None)
        else:
            world.set_tile(row=row, column=column, tile=selected)


# update runs each game step. Multiplying by dt makes speed mean pixels per second.
@stage.on_update
def update(event: Event[Stage, float]) -> None:
    dt = event.data
    direction = player.left_stick[0]
    hero.x = max(-360, min(1780, hero.x + direction * 220 * dt))


@stage.on_update
def show_selection(event: Event[Stage, float]) -> None:
    status.text = f"Camera x: {stage.camera[0]:.0f}    Paint: {selected}"


if __name__ == "__main__":
    stage.run()
