"""Dino Dash: jump cacti, duck birds, collect coins, and beat your best score."""

from pathlib import Path
from random import choice, random

from plocks import (
    Anchor,
    BodyType,
    Bounds,
    Box,
    Canvas,
    Click,
    Event,
    GamepadButton,
    GamepadPress,
    Image,
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

# Player one already has Space for jumping; map extra controls here.
player = stage.gamepads[0]
player.map_key(Key.DOWN, GamepadButton.B)
player.map_key(Key.P, GamepadButton.START)
player.map_key(Key.R, GamepadButton.SELECT)
player.map_key(Key.UP, GamepadButton.A)
GROUND = -130

desert = Image(assets / "desert.png").resized(width=800, height=450)
scenery = TiledBackground(desert, layer=-20)
stage.add(scenery)
sand = desert.cropped(x=0, y=418, width=32, height=32)
ground: list[TileMap] = []

# Our pictures share a feet anchor, so ducking keeps the feet in one place.
standing = Image(assets / "dinosaur.png", anchor=Anchor.BOTTOM_CENTER).resized(72, 72)
# Resizing keeps the feet anchor, even when we make the dinosaur shorter.
ducking = standing.resized(82, 38)
dino = Sprite(standing, x=-260, y=GROUND, layer=5)
stage.add(dino)
dino.body.shape = Box(38, 58, center=(6, 34))
dino.body.rotation_locked = True
dino.body.friction = 0

pictures = {
    "cactus": Image(assets / "cactus.png", anchor=Anchor.BOTTOM_CENTER).resized(44, 66),
    "rock": Image(assets / "rock.png", anchor=Anchor.BOTTOM_CENTER).resized(48, 36),
    "bird": Image(assets / "bird.png", anchor=Anchor.BOTTOM_CENTER).resized(64, 40),
}
coin_picture = Image(assets / "coin.png").resized(width=28, height=28)
cloud_picture = Image(assets / "cloud.png").resized(width=132, height=66)
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
coins = 0
best = 0
spawn_obstacle = Message[None]("spawn obstacle")
crashed = Message[None]("crashed")
spawning = dino.repeat().wait(1.4).broadcast(spawn_obstacle)


def score() -> int:
    """Work out the score instead of remembering another changing number."""
    return int(max(0, dino.x + 260) / 10) + coins * 25


def hitbox(actor: Sprite) -> Bounds:
    # Our colliders are upright boxes. Ignore the transparent picture padding.
    box = actor.body.shape
    assert isinstance(box, Box)
    x, y = actor.x + box.center[0], actor.y + box.center[1]
    return Bounds(x - box.width / 2, y - box.height / 2, x + box.width / 2, y + box.height / 2)


def extend_ground() -> None:
    # Add fixed floor sections ahead. The camera moves; these tiles never move.
    while not ground or ground[-1].bounds.right < stage.world_bounds.right + stage.width:
        x = ground[-1].bounds.right if ground else -432
        section = TileMap(
            ["G" * 27],
            {"G": sand},
            tile_size=(32, 32),
            solid={"G"},
            x=x,
            y=GROUND,
            layer=-5,
        )
        stage.add(section)
        ground.append(section)
        # One screen high keeps the camera level when the dinosaur jumps.
        stage.follow(
            dino,
            offset=(260, 0),
            bounds=Bounds(-432, -225, section.bounds.right, 225),
        )
    while ground[0].bounds.right < stage.world_bounds.left:
        stage.remove(ground.pop(0))


def reset() -> None:
    global playing, crouching, coins, best
    best = max(best, score())
    dino.stop()
    for section in ground:
        stage.remove(section)
    ground.clear()
    for actor in obstacles + pickups:
        stage.remove(actor)
    obstacles.clear()
    pickups.clear()
    playing, crouching = True, False
    coins = 0
    dino.image = standing
    dino.position = (-260, GROUND)
    dino.body.shape = Box(38, 58, center=(6, 34))
    dino.body.velocity = (0, 0)
    stage.camera = (0, 0)
    scenery.offset = (0, 0)
    for index, cloud in enumerate(clouds):
        cloud.x = -270 + index * 290
    extend_ground()
    stage.resume()
    dino.act(spawning)


@stage.on_start
def start(event: Event[Stage, None]) -> None:
    reset()


def try_jump() -> None:
    # Gravity brings us down. grounded stops a second jump in midair.
    if playing and not stage.paused and not crouching and dino.body.grounded:
        dino.body.impulse(y=460)


@dino.on_button_down(GamepadButton.A, gamepad=player)
def jump(event: Event[Sprite, GamepadPress]) -> None:
    try_jump()


@stage.on_click
def click_to_jump(event: Event[Stage, Click]) -> None:
    if event.data[1] == MouseButton.LEFT:
        try_jump()


@stage.on_button_down(GamepadButton.SELECT, gamepad=player)
def restart(event: Event[Stage, GamepadPress]) -> None:
    reset()


@stage.on_button_down(GamepadButton.START, gamepad=player)
def pause(event: Event[Stage, GamepadPress]) -> None:
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
    obstacle = Sprite(
        pictures[kind], x=stage.world_bounds.right + 60, y=y, body_type=BodyType.STATIC
    )
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
        coin = Sprite(coin_picture, x=obstacle.x + 160, y=GROUND + 105, body_type=BodyType.NONE)
        stage.add(coin)
        pickups.append(coin)


@stage.on_broadcast(crashed)
def game_over(event: Event[Stage, None]) -> None:
    global best
    best = max(best, score())
    stage.pause()


@stage.on_update
def update(event: Event[Stage, float]) -> None:
    global coins, playing, crouching
    if not playing:
        return
    distance = max(0, dino.x + 260)
    speed = min(480, 240 + distance / 60)
    dino.body.velocity = (speed, dino.body.velocity[1])
    extend_ground()
    # This decorative background uses screen coordinates, unlike our world tiles.
    scenery.offset = (-stage.camera[0] * 0.08, 0)
    for cloud in clouds:
        if cloud.bounds.right < stage.world_bounds.left:
            cloud.x = stage.world_bounds.right + cloud.image.width

    # Holding Down, S or gamepad B makes us small enough to pass a high bird.
    wants_duck = (
        player.left_stick[1] < 0
        or player.is_down(GamepadButton.B)
        or player.is_down(GamepadButton.DOWN)
    )
    if wants_duck != crouching and (crouching or dino.body.grounded):
        crouching = wants_duck
        dino.image = ducking if crouching else standing
        dino.body.shape = Box(52, 28, center=(6, 18)) if crouching else Box(38, 58, center=(6, 34))
    for obstacle in obstacles.copy():
        if obstacle.bounds.right < stage.world_bounds.left:
            stage.remove(obstacle)
            obstacles.remove(obstacle)
        elif hitbox(dino).intersects(hitbox(obstacle)) or dino.body.touching(obstacle.body):
            playing = False
            dino.stop()
            dino.broadcast(crashed)
            break
    # Use a copy when removing items while visiting a list.
    for coin in pickups.copy():
        collected = dino.touching(coin)
        if collected or coin.bounds.right < stage.world_bounds.left:
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
