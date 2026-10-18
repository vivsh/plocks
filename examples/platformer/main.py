"""Sky Steps: physical jumping, a moving lift, and a checkpoint."""

from pathlib import Path

from plocks import BodyType, Box, Canvas, Costume, Event, Key, Script, Sprite, Stage, TileMap

# Find assets beside this script, even when running from another folder.
assets = Path(__file__).resolve().parent / "assets"
stage = Stage(width=800, height=450, physics=True, background="#22364d")
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
lift = Sprite(assets / "platform.png", x=45, y=-110, body_type=BodyType.KINEMATIC)
stage.add(lift)
lift_trip = Script(Sprite).repeat()
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
    Costume(assets / "checkpoint.png", anchor=(4, 56)), x=180, y=37, body_type=BodyType.NONE
)
goal = Sprite(Costume(assets / "flag.png", anchor=(4, 100)), x=650, y=-150, body_type=BodyType.NONE)
stage.add(checkpoint)
stage.add(goal)
# These variables remember our progress. spawn is where we return after a fall.
spawn = (-300.0, -125.0)
saved = False
won = False
falls = 0


def respawn() -> None:
    """Return to the saved spot and stop any leftover falling speed."""
    hero.position = spawn
    hero.body.velocity = (0, 0)


# @ connects this function to a key press. grounded prevents jumping in midair.
@hero.on_key_down(Key.SPACE)
def jump(event: Event[Sprite, Key]) -> None:
    if hero.body.grounded and not won:
        hero.body.impulse(y=440)


@stage.on_key_down(Key.R)
def restart(event: Event[Stage, Key]) -> None:
    global spawn, saved, won, falls
    # global lets this function change the game variables at the top of this file.
    spawn = (-300, -125)
    saved = False
    won = False
    falls = 0
    hero.clear_bubble()
    respawn()


# Plocks calls update many times a second. dt is the time since the last game step.
@stage.on_update
def update(event: Event[Stage, float]) -> None:
    global spawn, saved, won, falls
    # Change sideways speed, but keep the up/down speed that physics calculated.
    speed_x = 0
    if not won:
        if stage.keyboard.is_down(Key.RIGHT):
            speed_x += 175
        if stage.keyboard.is_down(Key.LEFT):
            speed_x -= 175
    vertical_speed = hero.body.velocity[1]
    hero.body.velocity = (speed_x, vertical_speed)
    if not saved and hero.touching(checkpoint):
        spawn = (180, 62)
        saved = True
        hero.say("Checkpoint!", seconds=1)
    if hero.y < -300:
        falls += 1
        respawn()
    if hero.x > 620 and hero.body.grounded:
        won = True
    # Follow the hero, but stop the camera at the ends of the level.
    stage.camera = (max(0, min(350, hero.x - 20)), 0)


# Drawing adds words on top of the game. It does not move the characters.
@stage.on_draw
def draw(canvas: Canvas) -> None:
    canvas.text("SKY STEPS", (-380, 207), size=30, color="#ffd07a")
    checkpoint_text = "ahead"
    if saved:
        checkpoint_text = "saved"
    canvas.text(f"Falls: {falls}    Checkpoint: {checkpoint_text}", (-380, 170), size=22)
    canvas.text("Arrows: move   Space: jump   R: restart", (-380, -198), size=20)
    if won:
        canvas.text("You made it! Press R to replay.", (-220, 120), size=28)


if __name__ == "__main__":
    stage.run()
