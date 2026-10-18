"""Dino Dash: jump cacti, duck birds, collect coins, and beat your best score."""

from pathlib import Path
from random import choice, random

from plocks import (
    BodyType,
    Bounds,
    Box,
    Canvas,
    Click,
    Costume,
    Event,
    GamepadButton,
    GamepadPress,
    Key,
    Message,
    MouseButton,
    Sound,
    Sprite,
    Stage,
    TiledBackground,
    TileMap,
)

# Keep the pictures beside this file. No drawing program is needed in our code.
assets = Path(__file__).resolve().parent / "assets"
stage = Stage(width=800, height=450, physics=True, background="#fff0cc")
player = stage.gamepads[0]
player.map_key(Key.UP, GamepadButton.A)
GROUND = -130

desert = Costume(assets / "desert.png").resized(width=800, height=450)
scenery = TiledBackground(desert, layer=-20)
stage.add(scenery)
sand = desert.cropped(x=0, y=418, width=32, height=32)
ground = TileMap(
    ["G" * 27], {"G": sand}, tile_size=(32, 32), solid={"G"}, x=-432, y=GROUND, layer=-5
)
stage.add(ground)

# Our pictures share a feet anchor, so ducking keeps the feet in one place.
standing = Costume(assets / "dinosaur.png").resized(width=72, height=72).with_anchor(36, 72)
ducking = standing.resized(width=82, height=38).with_anchor(41, 38)
dino = Sprite(standing, x=-260, y=GROUND, layer=5)
stage.add(dino)
dino.body.shape = Box(38, 58, center=(6, 34))
dino.body.rotation_locked = True
dino.body.friction = 0

pictures = {
    "cactus": Costume(assets / "cactus.png").resized(width=44, height=66).with_anchor(22, 66),
    "rock": Costume(assets / "rock.png").resized(width=48, height=36).with_anchor(24, 36),
    "bird": Costume(assets / "bird.png").resized(width=64, height=40).with_anchor(32, 40),
}
coin_picture = Costume(assets / "coin.png").resized(width=28, height=28)
cloud_picture = Costume(assets / "cloud.png").resized(width=132, height=66)
pop = Sound(assets / "pop.ogg")
clouds: list[Sprite] = []
for x, y in ((-270, 110), (20, 150), (310, 95)):
    cloud = Sprite(cloud_picture, x=x, y=y, layer=-10, body_type=BodyType.NONE)
    stage.add(cloud)
    clouds.append(cloud)

# Lists remember the things currently on screen; each Sprite owns its position.
obstacles: list[Sprite] = []
pickups: list[Sprite] = []
playing = True
crouching = False
distance = 0.0
coins = 0
best = 0
spawn_obstacle = Message[None]("spawn obstacle")
crashed = Message[None]("crashed")
spawning = dino.repeat().wait(1.4).broadcast(spawn_obstacle)


def score() -> int:
    """Work out the score instead of remembering another changing number."""
    return int(distance / 10) + coins * 25


def reset() -> None:
    global playing, crouching, distance, coins, best
    best = max(best, score())
    dino.stop()
    for actor in obstacles + pickups:
        stage.remove(actor)
    obstacles.clear()
    pickups.clear()
    playing, crouching = True, False
    distance, coins = 0.0, 0
    dino.costume = standing
    dino.position = (-260, GROUND)
    dino.body.shape = Box(38, 58, center=(6, 34))
    dino.body.velocity = (0, 0)
    scenery.offset = (0, 0)
    stage.resume()
    dino.act(spawning)


@stage.on_start
def start(event: Event[Stage, None]) -> None:
    reset()


def try_jump() -> None:
    # Gravity brings us down. grounded stops a second jump in midair.
    if playing and not stage.paused and not crouching and dino.body.grounded:
        dino.body.impulse(y=460)


@dino.on_gamepad_button_down(GamepadButton.A, gamepad=player)
def jump(event: Event[Sprite, GamepadPress]) -> None:
    try_jump()


@stage.on_click
def click_to_jump(event: Event[Stage, Click]) -> None:
    if event.data[1] == MouseButton.LEFT:
        try_jump()


@stage.on_key_down(Key.R)
def restart(event: Event[Stage, Key]) -> None:
    reset()


@stage.on_key_down(Key.P)
def pause(event: Event[Stage, Key]) -> None:
    if playing:
        if stage.paused:
            stage.resume()
        else:
            stage.pause()


@stage.on_broadcast(spawn_obstacle)
def spawn(event: Event[Stage, None]) -> None:
    if not playing:
        return
    kinds = ("cactus", "rock", "bird") if score() >= 200 else ("cactus", "rock")
    kind = choice(kinds)
    y = GROUND + 46 if kind == "bird" else GROUND
    obstacle = Sprite(pictures[kind], x=460, y=y, body_type=BodyType.KINEMATIC)
    stage.add(obstacle)
    # Smaller hit boxes forgive the empty space around our pictures.
    if kind == "bird":
        obstacle.body.shape = Box(46, 24, center=(0, 19))
    elif kind == "rock":
        obstacle.body.shape = Box(32, 24, center=(0, 16))
    else:
        obstacle.body.shape = Box(24, 54, center=(0, 30))
    obstacles.append(obstacle)
    if random() < 0.7:
        coin = Sprite(coin_picture, x=620, y=GROUND + 105, body_type=BodyType.NONE)
        stage.add(coin)
        pickups.append(coin)


@stage.on_broadcast(crashed)
def game_over(event: Event[Stage, None]) -> None:
    global best
    best = max(best, score())
    stage.pause()


@stage.on_update
def update(event: Event[Stage, float]) -> None:
    global distance, coins, playing, crouching
    if not playing:
        return
    dt = event.data
    speed = min(480, 240 + distance / 60)
    distance += speed * dt
    scenery.offset = (-distance * 0.08, 0)
    for cloud in clouds:
        cloud.x -= speed * 0.18 * dt
        if cloud.x < -480:
            cloud.x = 480

    # Holding Down, S or gamepad B makes us small enough to pass a high bird.
    wants_duck = player.left_stick[1] < -0.5 or player.is_down(GamepadButton.B)
    wants_duck = wants_duck or stage.keyboard.is_down(Key.DOWN)
    if wants_duck != crouching and (crouching or dino.body.grounded):
        crouching = wants_duck
        dino.costume = ducking if crouching else standing
        dino.body.shape = Box(52, 28, center=(6, 18)) if crouching else Box(38, 58, center=(6, 34))
    for obstacle in obstacles.copy():
        obstacle.body.velocity = (-speed, 0)
        if obstacle.bounds.right < -420:
            stage.remove(obstacle)
            obstacles.remove(obstacle)
        elif dino.body.touching(obstacle.body):
            playing = False
            dino.stop()
            dino.broadcast(crashed)
            break
    # Use a copy when removing items while visiting a list.
    for coin in pickups.copy():
        coin.x -= speed * dt
        collected = dino.touching(coin)
        if collected or coin.x < -430:
            stage.remove(coin)
            pickups.remove(coin)
            if collected:
                coins += 1
                stage.play(pop, volume=0.25)


@stage.on_draw
def draw(canvas: Canvas) -> None:
    canvas.text("DINO DASH", (-375, 205), size=30, color="#24384b")
    canvas.text(
        f"Score {score()}   Coins {coins}   Best {best}", (-375, 167), size=21, color="#24384b"
    )
    canvas.rectangle(Bounds(-400, -225, 400, -180), color="#24384b")
    canvas.text(
        "Space / Up: jump    Down / S / F: duck    P: pause    R: restart",
        (-375, -198),
        size=18,
        color="#fff0cc",
    )
    if stage.paused:
        canvas.rectangle(Bounds(-215, -20, 215, 80), color="#24384b")
        text = "PAUSED — P to play" if playing else "BUMP! R to try again"
        canvas.text(text, (-185, 45), size=28, color="#fff0cc")


if __name__ == "__main__":
    stage.run()
