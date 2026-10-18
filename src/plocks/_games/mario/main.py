"""Coin Quest: a tiny Mario-style adventure with original artwork."""

from pathlib import Path

from plocks import (
    Bounds,
    Canvas,
    Costume,
    Event,
    Key,
    RotationStyle,
    Script,
    Sound,
    Sprite,
    Stage,
    TileMap,
)

# Find assets beside this script, even when running from another folder.
assets = Path(__file__).resolve().parent / "assets"
stage = Stage(width=800, height=450, background="#82bbcf")
# A row is a line of tiles: G = grass, D = dirt, S = stone, . = empty.
rows: list[str] = []
for _ in range(14):
    rows.append("." * 64)
rows[11] = "G" * 25 + "." * 3 + "G" * 36
rows[12] = rows[13] = "D" * 25 + "." * 3 + "D" * 36
rows[8] = "." * 12 + "SSSS" + "." * 16 + "SSSS" + "." * 28
world = TileMap(
    rows,
    {"G": assets / "grass.png", "D": assets / "dirt.png", "S": assets / "stone.png"},
    tile_size=(32, 32),
    solid={"G", "D", "S"},
    x=-400,
    y=224,
    layer=-1,
)
stage.add(world)
# The anchor is at the hero's feet, so hero.y is also the landing height.
hero = Sprite(Costume(assets / "hero.png", anchor=(16, 40)), x=-300, y=-128)
hero.rotation_style = RotationStyle.LEFT_RIGHT
stage.add(hero)
flag = Sprite(Costume(assets / "flag.png", anchor=(4, 100)), x=1550, y=-128)
stage.add(flag)
pop = Sound(assets / "pop.ogg")
# Lists keep track of the coins and enemies still in the game.
coins: list[Sprite] = []
enemies: list[Sprite] = []
speed_y = 0.0
on_ground = True
score = 0
outcome = "playing"


def finish(result: str) -> None:
    global outcome
    outcome = result
    for enemy in enemies:
        enemy.stop()


def reset() -> None:
    """Put back the coins, enemies and hero for a fresh try."""
    global speed_y, on_ground, score, outcome
    for actor in coins + enemies:
        stage.remove(actor)
    coins.clear()
    enemies.clear()
    hero.position = (-300, -128)
    hero.direction = 90
    speed_y = 0
    on_ground = True
    score = 0
    outcome = "playing"
    stage.camera = (0, 0)
    for x, y in (
        (-160, -80),
        (0, -80),
        (32, 15),
        (96, 15),
        (390, -20),
        (650, 50),
        (710, 50),
        (1050, -80),
        (1350, -80),
    ):
        coin = Sprite(assets / "coin.png", x=x, y=y)
        coins.append(coin)
        stage.add(coin)
    for x in (170, 850, 1250):
        enemy = Sprite(Costume(assets / "enemy.png", anchor=(16, 24)), x=x, y=-128)
        enemies.append(enemy)
        stage.add(enemy)
        patrol = Script(Sprite).repeat()
        patrol.glide_by(x=80, seconds=1)
        patrol.glide_by(x=-80, seconds=1)
        enemy.act(patrol)


def tile_bounds(row: int, column: int) -> Bounds:
    """Turn a tile's row and column into the edges of its box."""
    left = world.x + column * 32
    top = world.y - row * 32
    return Bounds(left, top - 32, left + 32, top)


# @ tells Plocks when to call jump. A held key is handled separately in update.
@hero.on_key_down(Key.SPACE)
def jump(event: Event[Sprite, Key]) -> None:
    # Change the variables at the top of this file, rather than creating new ones here.
    global speed_y, on_ground
    if on_ground and outcome == "playing":
        speed_y = 570
        on_ground = False


# dt is a small amount of time in seconds. Speed × dt gives this step's movement.
@stage.on_update
def update(event: Event[Stage, float]) -> None:
    dt = event.data
    global speed_y, on_ground, score
    if outcome != "playing":
        return
    direction = 0
    if stage.keyboard.is_down(Key.RIGHT):
        direction += 1
    if stage.keyboard.is_down(Key.LEFT):
        direction -= 1
    hero.x = max(-380, min(1600, hero.x + direction * 200 * dt))
    if direction > 0:
        hero.direction = 90
    elif direction < 0:
        hero.direction = 270
    # First fix sideways overlap with walls, then handle jumping and landing.
    for row, col in world.tiles_touching(hero.bounds):
        tile = tile_bounds(row, col)
        if direction > 0:
            hero.x += tile.left - hero.bounds.right
        elif direction < 0:
            hero.x += tile.right - hero.bounds.left
    previous_feet = hero.y
    # Gravity reduces upward speed until the hero starts falling.
    speed_y -= 1400 * dt
    hero.y += speed_y * dt
    on_ground = False
    contacts = world.tiles_touching(hero.bounds)
    for row, col in contacts:
        tile = tile_bounds(row, col)
        if speed_y < 0:
            hero.y = max(hero.y, tile.top)
            on_ground = True
        else:
            hero.y -= hero.bounds.top - tile.bottom
    if contacts:
        speed_y = 0
    # Walk through a copy so removing a collected coin does not skip the next one.
    for coin in coins.copy():
        if hero.touching(coin):
            coins.remove(coin)
            stage.remove(coin)
            score += 1
            stage.play(pop, volume=0.2)
    # Falling onto an enemy gives a bounce; touching its side ends the run.
    for enemy in enemies.copy():
        if hero.touching(enemy):
            if speed_y < 0 and previous_feet >= enemy.bounds.top - 4:
                enemies.remove(enemy)
                stage.remove(enemy)
                speed_y = 380
            else:
                finish("Try again!")
    if hero.y < -300:
        finish("Mind the gap!")
    elif hero.x >= flag.x and outcome == "playing":
        finish("You reached the flag!")
    stage.camera = (max(0, min(1248, hero.x - 40)), 0)


# f-strings put our changing score inside the words on screen.
@stage.on_draw
def draw(canvas: Canvas) -> None:
    canvas.text(f"COIN QUEST    Coins {score}/9", (-380, 207), color="#183344", size=28)
    canvas.text("Arrows: run   Space: jump   R: restart", (-380, -198), size=20)
    if outcome != "playing":
        canvas.rectangle(Bounds(-260, -40, 260, 70), color="#183344")
        canvas.text(outcome, (-220, 45), size=30)
        canvas.text("Press R to try again", (-150, 0), size=24)


@stage.on_key_down(Key.R)
def restart(event: Event[Stage, Key]) -> None:
    reset()


reset()


if __name__ == "__main__":
    stage.run()
