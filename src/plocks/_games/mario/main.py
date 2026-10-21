"""Coin Quest: let physics handle jumping while you collect coins and dodge enemies."""

from pathlib import Path

from plocks import (
    Anchor,
    BodyType,
    Bounds,
    Box,
    Canvas,
    Event,
    GamepadButton,
    GamepadPress,
    Image,
    Key,
    RotationStyle,
    Sound,
    Sprite,
    Stage,
    TileMap,
)

# Find pictures beside this file, even when running from another folder.
assets = Path(__file__).resolve().parent / "assets"
stage = Stage(width=800, height=450, physics=True, background="#82bbcf")
stage.physics.gravity = (0, -1400)
player = stage.gamepads[0]
# Space already jumps. Add arrow movement and R to restart.
player.map_left_stick(left=Key.LEFT, right=Key.RIGHT)
player.map_key(Key.R, GamepadButton.SELECT)

# G = grass, D = dirt, S = stone, . = empty. Solid tiles do the landing work.
rows = ["." * 64] * 14
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
hero = Sprite(assets / "hero.png", x=-300, y=-108)
hero.rotation_style = RotationStyle.LEFT_RIGHT
stage.add(hero)
# Keep the body centered and upright; bounds.bottom tells us where its feet are.
hero.body.shape = Box(32, 40)
hero.body.rotation_locked = True
hero.body.friction = 0
flag = Sprite(Image(assets / "flag.png", anchor=(4, 100)), x=1550, y=-128, body_type=BodyType.NONE)
stage.add(flag)
stage.follow(hero, offset=(-40, 0), bounds=Bounds(-400, -225, 1648, 225))
pop = Sound(assets / "pop.ogg")
enemy_picture = Image(assets / "enemy.png", anchor=Anchor.BOTTOM_CENTER)
coins: list[Sprite] = []
enemies: list[Sprite] = []
score = 0
outcome = "playing"


def finish(result: str) -> None:
    global outcome
    outcome = result
    # Pause freezes physics too. The restart button still works while paused.
    stage.pause()


def reset() -> None:
    """Put back the coins, enemies and hero for a fresh try."""
    global score, outcome
    for actor in coins + enemies:
        stage.remove(actor)
    coins.clear()
    enemies.clear()
    hero.stop()
    hero.position = (-300, -108)
    hero.direction = 90
    hero.body.velocity = (0, 0)
    score = 0
    outcome = "playing"
    stage.resume()
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
        coin = Sprite(assets / "coin.png", x=x, y=y, body_type=BodyType.NONE)
        coins.append(coin)
        stage.add(coin)
    for x in (170, 850, 1250):
        enemy = Sprite(enemy_picture, x=x, y=-128, body_type=BodyType.NONE)
        enemies.append(enemy)
        stage.add(enemy)
        patrol = enemy.repeat()
        patrol.glide_by(x=80, seconds=1)
        patrol.glide_by(x=-80, seconds=1)
        enemy.act(patrol)


@hero.on_button_down(GamepadButton.A, gamepad=player)
def jump(event: Event[Sprite, GamepadPress]) -> None:
    # grounded prevents another jump in the air. Physics brings us back down.
    if hero.body.grounded and outcome == "playing":
        hero.body.impulse(y=570)


@stage.on_update
def update(event: Event[Stage, float]) -> None:
    global score
    if outcome != "playing":
        return
    direction = player.left_stick[0]
    # Push sideways, letting walls push back. Limit speed instead of forcing
    # a new forward velocity into a wall on every step.
    vx, vy = hero.body.velocity
    if direction == 0:
        vx = 0
    hero.body.velocity = (max(-200, min(200, vx)), vy)
    if direction:
        hero.body.force(x=direction * 1800)
    if hero.x < -380:
        hero.x = -380
    elif hero.x > 1600:
        hero.x = 1600
    if direction > 0 and hero.direction != 90:
        hero.direction = 90
    elif direction < 0 and hero.direction != 270:
        hero.direction = 270
    # A copy lets us remove a collected coin without skipping the next one.
    for coin in coins.copy():
        if hero.touching(coin):
            coins.remove(coin)
            stage.remove(coin)
            score += 1
            stage.play(pop, volume=0.2)
    for enemy in enemies.copy():
        if hero.touching(enemy):
            # Falling onto the top half gives a bounce; a side hit ends the run.
            if hero.body.velocity[1] < 0 and hero.bounds.bottom > enemy.bounds.center[1]:
                enemies.remove(enemy)
                stage.remove(enemy)
                hero.body.velocity = (hero.body.velocity[0], 380)
            else:
                finish("Try again!")
    if hero.bounds.bottom < -300:
        finish("Mind the gap!")
    elif hero.x >= flag.x and outcome == "playing":
        finish("You reached the flag!")


@stage.on_draw
def draw(canvas: Canvas) -> None:
    canvas.text(f"COIN QUEST    Coins {score}/9", (-380, 207), color="#183344", size=28)
    canvas.text("Arrows: run   Space: jump   R: restart", (-380, -198), size=20)
    if outcome != "playing":
        canvas.rectangle(Bounds(-260, -40, 260, 70), color="#183344")
        canvas.text(outcome, (-220, 45), size=30)
        canvas.text("Press R to try again", (-150, 0), size=24)


@stage.on_button_down(GamepadButton.SELECT, gamepad=player)
def restart(event: Event[Stage, GamepadPress]) -> None:
    reset()


@stage.on_start
def start(event: Event[Stage, None]) -> None:
    reset()


if __name__ == "__main__":
    stage.run()
