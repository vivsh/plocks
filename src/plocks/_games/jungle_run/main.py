"""Jungle Run: run, jump and shoot your way past six robots.

Physics handles jumping and landing. Try Sky Steps before the bullet rules here.
"""

from math import sin
from pathlib import Path

from plocks import (
    Action,
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
    Message,
    RotationStyle,
    Sprite,
    Stage,
    TileMap,
)

# Find assets beside this script, even when running from another folder.
assets = Path(__file__).resolve().parent / "assets"
stage = Stage(width=800, height=450, physics=True, background="#102735")
stage.physics.gravity = (0, -1500)

# Player one already has Space for jumping; map extra controls here.
player = stage.gamepads[0]
player.map_left_stick(left=Key.LEFT, right=Key.RIGHT)
player.map_key(Key.P, GamepadButton.START)
player.map_key(Key.R, GamepadButton.SELECT)
player.map_key(Key.X, GamepadButton.X)
# This distant layer scrolls automatically at 22% of the camera's speed.
backdrop = TileMap(
    ["J" * 5],
    {"J": assets / "jungle.png"},
    tile_size=(256, 450),
    x=-400,
    y=225,
    layer=-100,
    parallax=(0.22, 0),
)
stage.add(backdrop)

# Each # makes a ground tile. Lower layers are drawn behind the hero.
ground = TileMap(
    ["#" * 70] * 3,
    {"#": assets / "ground.png"},
    tile_size=(32, 32),
    solid={"#"},
    x=-400,
    y=-150,
    layer=-5,
)
stage.add(ground)

platforms: list[Sprite] = []
for x, y, width in ((100, -86, 160), (390, -22, 160), (910, -86, 170), (1450, -86, 150)):
    platform = Sprite(
        Image(assets / f"ledge{width}.png", anchor=(0, 0)),
        x=x,
        y=y,
        layer=-2,
        body_type=BodyType.STATIC,
        one_way=True,
    )
    platforms.append(platform)
    stage.add(platform)

stage.add(
    Sprite(
        Image(assets / "flag.png", anchor=(4, 100)),
        x=1720,
        y=-150,
        layer=-1,
        body_type=BodyType.NONE,
    )
)

idle = Image(assets / "hero.png")
# Equal-sized centered images can take turns without moving the hero.
walking_frames = (
    Image(assets / "walk1.png"),
    Image(assets / "walk2.png"),
)
walking: Action | None = None
hero = Sprite(idle, x=-300, y=-120, scale=1.5, layer=2)
hero.rotation_style = RotationStyle.LEFT_RIGHT
stage.add(hero)
# A centered body keeps the same hitbox when we face left or right.
hero.body.shape = Box(28, 40)
hero.body.rotation_locked = True
hero.body.friction = 0
stage.follow(hero, offset=(-60, 0), bounds=Bounds(-400, -225, 1800, 225))
sentry = Image(assets / "robot.png", anchor=Anchor.BOTTOM_CENTER)
friendly_shot = Image(assets / "friendly_shot.png")
hostile_shot = Image(assets / "hostile_shot.png")
enemies: list[Sprite] = []
# A shot stores (sprite, sideways speed, friendly). True means the hero fired it.
shots: list[tuple[Sprite, float, bool]] = []
protected_until = 0.0
health = 3
defeated = 0


def finished() -> bool:
    return health <= 0 or (not enemies and hero.x >= 1680)


def fire(actor: Sprite, friendly: bool) -> None:
    """Make a bullet. The hero aims forward; robots aim toward the hero."""
    direction = 1
    if friendly:
        image = friendly_shot
        speed = 560
        height = actor.y + 2
        if actor.direction != 90:
            direction = -1
    else:
        image = hostile_shot
        speed = 230
        height = actor.y + 32
        if hero.x <= actor.x:
            direction = -1
    shot = Sprite(
        image,
        x=actor.x + direction * 30,
        y=height,
        layer=3,
        body_type=BodyType.NONE,
    )
    stage.add(shot)
    shots.append((shot, direction * speed, friendly))


fire_requested = Message[None]("enemy fire requested")
patrol = hero.repeat().glide_by(x=45, seconds=1.2).glide_by(x=-45, seconds=1.2)
firing = hero.repeat().wait(1.5).broadcast(fire_requested)
sentry_behavior = hero.sequence().during(patrol, meanwhile=firing)


@stage.on_broadcast(fire_requested)
def fire_when_near(event: Event[Stage, None]) -> None:
    enemy = event.source
    if not isinstance(enemy, Sprite) or enemy not in enemies:
        return
    if not finished() and abs(enemy.x - hero.x) < 480:
        enemy.direction = 270 if hero.x <= enemy.x else 90
        fire(enemy, False)


def spawn_enemies() -> None:
    for x, y in ((140, -150), (440, -22), (730, -150), (970, -86), (1260, -150), (1490, -86)):
        enemy = Sprite(sentry, x=x, y=y, scale=1.5, layer=1, body_type=BodyType.NONE)
        enemy.rotation_style = RotationStyle.LEFT_RIGHT
        stage.add(enemy)
        enemies.append(enemy)
        # Every robot uses the same script. Its firing message identifies its sender.
        enemy.act(sentry_behavior)


def remove_shot(shot: tuple[Sprite, float, bool]) -> None:
    shots.remove(shot)
    stage.remove(shot[0])


def hurt() -> None:
    """Lose one health point, then give the hero a short safe moment."""
    global health, protected_until
    if stage.time < protected_until or health <= 0:
        return
    health -= 1
    protected_until = stage.time + 1.3
    if health == 0:
        hero.stop()
        for enemy in enemies:
            enemy.stop()
        hero.image = idle
        hero.visible = True
        stage.pause()


# grounded stops air jumps; physics brings the hero back to the platforms.
@hero.on_button_down(GamepadButton.A, gamepad=player)
def jump(event: Event[Sprite, GamepadPress]) -> None:
    if not finished() and hero.body.grounded:
        hero.body.impulse(y=650)


# Turbo repeats for us while X stays held; no cooldown timer is needed.
@hero.on_button_down(GamepadButton.X, gamepad=player, repeat=0.16)
def shoot(event: Event[Sprite, GamepadPress]) -> None:
    if not finished() and not stage.paused:
        fire(event.target, True)


@stage.on_button_down(GamepadButton.SELECT, gamepad=player)
def restart(event: Event[Stage, GamepadPress]) -> None:
    global health, defeated, protected_until
    hero.stop()
    for enemy in enemies:
        stage.remove(enemy)
    enemies.clear()
    # A copy lets us remove bullets without skipping the next one in the list.
    for shot in shots.copy():
        remove_shot(shot)
    hero.position = (-300, -120)
    hero.direction = 90
    hero.image = idle
    hero.visible = True
    hero.body.velocity = (0, 0)
    health = 3
    defeated = 0
    protected_until = stage.time + 1
    stage.resume()
    spawn_enemies()


@stage.on_button_down(GamepadButton.START, gamepad=player)
def toggle_pause(event: Event[Stage, GamepadPress]) -> None:
    if stage.paused:
        stage.resume()
    else:
        stage.pause()


# dt is the time since the last game step. Speed × dt gives the distance to move.
@stage.on_update
def update(event: Event[Stage, float]) -> None:
    dt = event.data
    global defeated, walking
    if finished():
        if walking is not None:
            walking.cancel()
        hero.image = idle
        hero.visible = True
        stage.pause()
        return
    direction = player.left_stick[0]
    hero.body.velocity = (direction * 220, hero.body.velocity[1])
    if hero.x < -365:
        hero.x = -365
    elif hero.x > 1770:
        hero.x = 1770
    if direction > 0 and hero.direction != 90:
        hero.direction = 90
    elif direction < 0 and hero.direction != 270:
        hero.direction = 270
    if direction and hero.body.grounded:
        if walking is None or walking.done:
            walking = hero.act(hero.repeat().images(walking_frames, fps=9))
    else:
        if walking is not None:
            walking.cancel()
        hero.image = idle

    # Blink during the safe moment after a hit. % 2 alternates between zero and one.
    hero.visible = stage.time >= protected_until or int(stage.time * 12) % 2 == 0
    # A copy lets us remove bullets without skipping the next one in the list.
    for shot in shots.copy():
        sprite, speed, friendly = shot
        previous = sprite.bounds
        sprite.x += speed * dt
        current = sprite.bounds
        # Check the whole path since the last step, so a fast bullet cannot skip a robot.
        swept = Bounds(
            min(previous.left, current.left),
            current.bottom,
            max(previous.right, current.right),
            current.top,
        )
        hit_platform = False
        for platform in platforms:
            if swept.intersects(platform.bounds):
                hit_platform = True
                break
        if abs(sprite.x - hero.x) > 650 or hit_platform:
            remove_shot(shot)
            continue
        if friendly:
            target = None
            for enemy in enemies:
                if swept.intersects(enemy.bounds):
                    target = enemy
                    break
            if target is not None:
                stage.remove(target)
                enemies.remove(target)
                defeated += 1
                remove_shot(shot)
        elif swept.intersects(hero.bounds):
            remove_shot(shot)
            hurt()
    for enemy in enemies:
        if hero.touching(enemy):
            hurt()
            break


@stage.on_draw
def draw(canvas: Canvas) -> None:
    canvas.rectangle(Bounds(-400, 177, 400, 225), color="#0c1c29")
    canvas.text("JUNGLE RUN", (-380, 212), size=28, color="#edc46e")
    canvas.text(f"HEALTH {'|' * health}    SENTRIES {defeated}/6", (-150, 207), size=22)
    canvas.text(
        "Arrows: move   Space: jump   Hold X: fire   P: pause   R: restart",
        (-380, -197),
        size=20,
    )
    canvas.text(
        "Clear the sentries, then reach the gold flag.", (-380, 167), size=18, color="#abd2bc"
    )
    if finished() or stage.paused:
        canvas.rectangle(Bounds(-260, -45, 260, 65), color="#0c1c29")
        title = "PAUSED"
        if health <= 0:
            title = "TRY AGAIN"
        elif finished():
            title = "MISSION CLEAR!"
        canvas.text(title, (-110, 40), size=34, color="#edc46e")
        instruction = "Press P to continue"
        if finished():
            instruction = "Press R to restart"
        canvas.text(instruction, (-105, -5), size=23)
    else:
        # A pulsing light marks the extraction point ahead.
        goal_x = 1720 - stage.camera[0]
        if -390 < goal_x < 390:
            canvas.circle((goal_x, -42), 3 + sin(stage.time * 4), color="#edc46e")


spawn_enemies()


if __name__ == "__main__":
    stage.run()
