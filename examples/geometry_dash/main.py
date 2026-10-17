"""Beat Blocks: a short auto-running jump course."""

from pathlib import Path

from plocks import Bounds, Canvas, Key, Sound, Sprite, Stage, TileMap

# Keep assets beside this file so the game also works from another folder.
assets = Path(__file__).resolve().with_name("assets")
stage = Stage(width=800, height=450, background="#19253d")
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
hero = Sprite(assets / "cube.png", x=-240, y=-124)
stage.add(hero)
spikes: list[Sprite] = []
# Change these x positions to design your own obstacle course.
for x in (40, 280, 520, 552, 840, 1100, 1132, 1420, 1680, 1712, 2000):
    spike = Sprite(assets / "spike.png", x=x, y=-124)
    stage.add(spike)
    spikes.append(spike)
pop = Sound(assets / "pop.ogg")
# Positive speed_y goes up. Gravity will pull it back down.
speed_y = 0.0
outcome = "playing"
attempts = 1


# @ connects this function to Space. Only jump when the cube is on the floor.
@hero.on_key_down(Key.SPACE)
def jump() -> None:
    # global lets this helper change speed_y at the top of this file.
    global speed_y
    if outcome == "playing" and hero.y == -124:
        speed_y = 540


@stage.on_key_down(Key.R)
def restart() -> None:
    global speed_y, outcome, attempts
    hero.position = (-240, -124)
    hero.direction = 90
    speed_y = 0
    outcome = "playing"
    attempts += 1
    stage.camera = (0, 0)


# Plocks runs update each game step. dt is that step's length in seconds.
@stage.on_update
def update(dt: float) -> None:
    global speed_y, outcome
    if outcome != "playing":
        return
    # Speed × time tells us how far to move. The cube runs without a held key.
    hero.x += 230 * dt
    speed_y -= 1600 * dt
    # max keeps the cube from falling below the floor.
    hero.y = max(-124, hero.y + speed_y * dt)
    if hero.y == -124:
        speed_y = 0
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
            stage.play(pop, volume=0.2)
            break
    if hero.x >= 2200:
        outcome = "Course complete!"
    stage.camera = (max(0, hero.x + 120), 0)


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
