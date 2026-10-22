"""Sky Steps: physical jumping, a moving lift, and a checkpoint."""

from pathlib import Path

from plocks import (
    AlertLevel,
    Anchor,
    BodyType,
    Bounds,
    Box,
    Event,
    GamepadButton,
    GamepadPress,
    Image,
    Key,
    Label,
    Sprite,
    Stage,
    TileMap,
    UITheme,
)

# Find assets beside this script, even when running from another folder.
assets = Path(__file__).resolve().parent / "assets"
stage = Stage(
    width=800,
    height=450,
    physics=True,
    background="#22364d",
    ui_theme=UITheme(accent_color="#ffd07a"),
)

# Player one already has Space for jumping. Add arrows and R for this game.
player = stage.gamepads[0]
player.map_left_stick(left=Key.LEFT, right=Key.RIGHT)
player.map_key(Key.R, GamepadButton.SELECT)
# G means grass; a dot leaves a gap. Each letter makes one 32-pixel tile.
ground = TileMap(
    ["GGGGGGGG.................GGGGGGGGGGGG"],
    {"G": assets / "grass.png"},
    tile_size=(32, 32),
    solid={"G"},
    x=-400,
    y=-150,
    layer=-1,
)
stage.add(ground)
# Static platforms stay put. A kinematic platform follows our movement script.
for x, y in ((-90, -90), (180, 30), (380, -40)):
    ledge = Sprite(assets / "platform.png", x=x, y=y, body_type=BodyType.STATIC)
    stage.add(ledge)
# Jump through the lift from below, then land on its top.
lift = Sprite(assets / "platform.png", x=45, y=-110, body_type=BodyType.KINEMATIC, one_way=True)
stage.add(lift)
lift_trip = lift.repeat()
lift_trip.glide_to(y=65, seconds=2)
lift_trip.wait(0.5)
lift_trip.glide_to(y=-110, seconds=2)
lift_trip.wait(0.5)
lift.on_start(lift_trip)
hero = Sprite(assets / "hero.png", x=-300, y=-125)
stage.add(hero)
# Physics handles falling and landing. Lock rotation so our hero stays upright.
hero.body.shape = Box(24, 40)
hero.body.rotation_locked = True
checkpoint = Sprite(
    Image(assets / "checkpoint.png", anchor=(4, 56)), x=180, y=37, body_type=BodyType.NONE
)
goal = Sprite(Image(assets / "flag.png", anchor=(4, 100)), x=650, y=-150, body_type=BodyType.NONE)
stage.add(checkpoint)
stage.add(goal)
# Follow sideways, keeping the window inside this stretch of the level.
stage.follow(hero, offset=(-20, 0), bounds=Bounds(-400, -225, 750, 225))
# These variables remember our progress. spawn is where we return after a fall.
spawn = (-300.0, -125.0)
saved = False
won = False
falls = 0


# Labels stay on the screen while the camera follows the hero.
title = Label("SKY STEPS", position=(-380, 207), anchor=Anchor.TOP_LEFT, color="#ffd07a", size=30)
status = Label(
    "Falls: 0    Checkpoint: ahead", position=(-380, 165), anchor=Anchor.TOP_LEFT, size=22
)
help_text = Label("Arrows: move   Space: jump   R: restart", position=(0, -205), size=20)
for control in (title, status, help_text):
    stage.add(control)


def respawn() -> None:
    """Return to the saved spot and stop any leftover falling speed."""
    hero.position = spawn
    hero.body.velocity = (0, 0)


# @ connects this function to a key press. grounded prevents jumping in midair.
@hero.on_button_down(GamepadButton.A, gamepad=player)
def jump(event: Event[Sprite, GamepadPress]) -> None:
    if hero.body.grounded and not won:
        hero.body.impulse(y=440)


def reset() -> None:
    global spawn, saved, won, falls
    # global lets this function change the game variables at the top of this file.
    spawn = (-300, -125)
    saved = False
    won = False
    falls = 0
    hero.clear_bubble()
    respawn()
    status.text = "Falls: 0    Checkpoint: ahead"


@stage.on_button_down(GamepadButton.SELECT, gamepad=player)
def restart(event: Event[Stage, GamepadPress]) -> None:
    reset()


def play_again(event: Event[Stage, None]) -> None:
    reset()


# Plocks calls update many times a second. dt is the time since the last game step.
@stage.on_update
def update(event: Event[Stage, float]) -> None:
    global spawn, saved, won, falls
    # Change sideways speed, but keep the up/down speed that physics calculated.
    speed_x = player.left_stick[0] * 175 if not won else 0
    vertical_speed = hero.body.velocity[1]
    hero.body.velocity = (speed_x, vertical_speed)
    if not saved and hero.touching(checkpoint):
        spawn = (180, 62)
        saved = True
        hero.say("Checkpoint!", seconds=1)
    if hero.y < -300:
        falls += 1
        respawn()
    checkpoint_text = "saved" if saved else "ahead"
    status.text = f"Falls: {falls}    Checkpoint: {checkpoint_text}"
    if not won and hero.x > 620 and hero.body.grounded:
        won = True
        stage.alert(
            "You reached the flag!",
            level=AlertLevel.SUCCESS,
            button_text="Play again",
            on_close=play_again,
        )


if __name__ == "__main__":
    stage.run()
