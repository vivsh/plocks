"""Beat Blocks: a short auto-running jump course."""

from pathlib import Path

from plocks import (
    Action,
    Bounds,
    Canvas,
    Ease,
    Event,
    GamepadButton,
    GamepadPress,
    Image,
    Key,
    Sound,
    Sprite,
    Stage,
    TileMap,
)

# Find assets beside this script, even when running from another folder.
assets = Path(__file__).resolve().parent / "assets"
stage = Stage(width=800, height=450, background="#19253d")

# Player one already has Space for jumping; map extra controls here.
player = stage.gamepads[0]
player.map_key(Key.R, GamepadButton.SELECT)
# Repeat a stone tile to make the floor. layer=-1 puts it behind the hero.
ground = TileMap(
    ["#" * 100] * 2,
    {"#": assets / "stone.png"},
    tile_size=(32, 32),
    solid={"#"},
    x=-400,
    y=-140,
    layer=-1,
)
stage.add(ground)
hero = Sprite(
    Image.rectangle(32, 32, color="#ffe16a", outline="#fff0b0", outline_width=3), x=-240, y=-124
)
stage.add(hero)
# Follow the cube through the world. One-screen-high bounds keep jumps from moving the view up.
stage.follow(
    hero, offset=(120, 0), bounds=Bounds(ground.bounds.left, -225, ground.bounds.right, 225)
)
spikes: list[Sprite] = []
# Change these x positions to design your own obstacle course.
for x in (40, 280, 520, 552, 840, 1100, 1132, 1420, 1680, 1712, 2000):
    spike = Sprite(Image.triangle(32, 32, color="#f06499", outline="#ffb0cf"), x=x, y=-124)
    stage.add(spike)
    spikes.append(spike)
pop = Sound(assets / "pop.ogg")
outcome = "playing"
attempts = 1


# @ connects this function to Space. Only jump when the cube is on the floor.
@hero.on_button_down(GamepadButton.A, gamepad=player)
def jump(event: Event[Sprite, GamepadPress]) -> Action | None:
    if outcome != "playing" or hero.y != -124:
        return None
    # after joins the two halves. Returning the action keeps this jump busy.
    up = hero.glide_by(y=100, seconds=0.35, easing=Ease.OUT)
    return hero.glide_by(y=-100, seconds=0.35, easing=Ease.IN, after=up)


@stage.on_button_down(GamepadButton.SELECT, gamepad=player)
def restart(event: Event[Stage, GamepadPress]) -> None:
    global outcome, attempts
    hero.stop()
    hero.position = (-240, -124)
    hero.direction = 90
    outcome = "playing"
    attempts += 1


# Plocks runs update each game step. dt is that step's length in seconds.
@stage.on_update
def update(event: Event[Stage, float]) -> None:
    dt = event.data
    global outcome
    if outcome != "playing":
        return
    # Speed × time tells us how far to move. The cube runs without a held key.
    hero.x += 230 * dt
    if hero.y == -124:
        hero.direction = 90
    else:
        hero.direction += 360 * dt
    # A hitbox is an invisible box used to test a crash.
    # These boxes are a little smaller than the pictures, to make near misses fair.
    body = Bounds(hero.x - 12, hero.y - 12, hero.x + 12, hero.y + 12)
    for spike in spikes:
        danger = Bounds(spike.x - 8, -140, spike.x + 8, -116)
        if body.intersects(danger):
            outcome = "Crash!"
            hero.stop()
            stage.play(pop, volume=0.2)
            break
    if hero.x >= 2200:
        outcome = "Course complete!"
        hero.stop()


# Draw the score and instructions after the sprites, so they stay on top.
@stage.on_draw
def draw(canvas: Canvas) -> None:
    progress = min(100, int((hero.x + 240) / 2440 * 100))
    canvas.text(f"BEAT BLOCKS    {progress}%    Attempt {attempts}", (-380, 207), size=27)
    canvas.text("Space: jump   R: restart    Time your jumps!", (-380, -198), size=20)
    if outcome != "playing":
        canvas.text(outcome + " Press R.", (-200, 40), size=32, color="#ffd782")


if __name__ == "__main__":
    stage.run()
