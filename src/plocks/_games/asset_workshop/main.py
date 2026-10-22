"""Play with an exported level, animation, and two sets of player controls."""

from pathlib import Path

from plocks import (
    Anchor,
    Ease,
    Event,
    GamepadButton,
    GamepadLayout,
    GamepadPress,
    Key,
    Label,
    Panel,
    PixeloramaSheet,
    Sprite,
    Stage,
    TiledMap,
)

assets = Path(__file__).resolve().parent / "assets"
# A fixed camera shows both players and the whole small level.
stage = Stage(width=640, height=400, background="#203548")

# The first two players already have separate keyboard controls.
one, two = stage.gamepads[:2]
one.map_key(Key.E, GamepadButton.Y)

# Tiled gives us ordinary tile maps and named places to start.
level = TiledMap(assets / "jungle.tmj", x=-160, y=64, layer=-1)
for tilemap in level.layers.values():
    stage.add(tilemap)

# Pixelorama remembers the pictures and how long each one lasts.
art = PixeloramaSheet(assets / "hero.png")
hero = Sprite(art.frames[0])
hero.position = level.points["Spawns/player_start"]
friend = Sprite(art.frames[0], x=100, y=-44)
stage.add(hero)
stage.add(friend)
hero.on_start(art.animation("walk").repeat())
friend.on_start(art.animation("walk").repeat())

# The first two players already have keyboard controls. Controllers work too.
two.layout = GamepadLayout.NINTENDO

# One script can run on either character, with its own starting position.
jump = hero.sequence()
jump.glide_by(y=80, seconds=0.25, easing=Ease.OUT)
jump.glide_by(y=-80, seconds=0.25, easing=Ease.IN)
hero.on_button_down(GamepadButton.A, jump, gamepad=one)
friend.on_button_down(GamepadButton.A, jump, gamepad=two)


# One panel groups the instructions; no drawing callback is needed.
help_panel = Panel(position=(0, 160), width=640, height=80)
help_panel.add(
    Label(
        "1: A D / Space / F     2: arrows / Enter / R Shift",
        position=(-300, 18),
        anchor=Anchor.CENTER_LEFT,
        size=18,
    )
)
help_panel.add(
    Label(
        "Controllers: stick / A / B     E: change a tile",
        position=(-300, -12),
        anchor=Anchor.CENTER_LEFT,
        size=18,
    )
)
stage.add(help_panel)


@hero.on_update
@friend.on_update
def move(event: Event[Sprite, float]) -> None:
    # Both use the same rule; target tells us which character needs to move.
    gamepad = one if event.target is hero else two
    event.target.x += gamepad.left_stick[0] * 120 * event.data


@hero.on_button_down(GamepadButton.B, gamepad=one, repeat=0.2)
def hero_speaks(event: Event[Sprite, GamepadPress]) -> None:
    # Turbo repeats while B (or F) stays held. A jump still happens just once.
    event.target.say("Pew!", seconds=0.15)


@friend.on_button_down(GamepadButton.B, gamepad=two, repeat=0.2)
def friend_speaks(event: Event[Sprite, GamepadPress]) -> None:
    event.target.say("Pop!", seconds=0.15)


@stage.on_button_down(GamepadButton.Y, gamepad=one)
def edit_ground(event: Event[Stage, GamepadPress]) -> None:
    # Imported cells can be edited just like a hand-made tile map.
    ground = level.layers["Ground"]
    tile = None if ground.get_tile(row=4, column=5) else "1"
    ground.set_tile(row=4, column=5, tile=tile)


if __name__ == "__main__":
    stage.run()
