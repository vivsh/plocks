"""Jungle Run: run, jump and shoot your way past six robots.

This bigger example writes its own jump and bullet rules. Try Sky Steps first.
"""

from math import sin
from pathlib import Path

from plocks import (
    Action,
    Bounds,
    Canvas,
    Costume,
    Key,
    RotationStyle,
    Sprite,
    Stage,
    TiledBackground,
    TileMap,
)

# Find the pictures beside main.py, even when running from another folder.
assets = Path(__file__).resolve().with_name("assets")
stage = Stage(width=800, height=450, background="#102735")
backdrop = TiledBackground(assets / "jungle.png")
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
    platform = Sprite(Costume(assets / f"ledge{width}.png", anchor=(0, 0)), x=x, y=y, layer=-2)
    platforms.append(platform)
    stage.add(platform)

stage.add(Sprite(Costume(assets / "flag.png", anchor=(4, 100)), x=1720, y=-150, layer=-1))

idle = Costume(assets / "hero.png", anchor=(14, 40))
# Anchors put each costume's feet at the same point when we swap pictures.
walking_frames = (
    Costume(assets / "walk1.png", anchor=(14, 40)),
    Costume(assets / "walk2.png", anchor=(14, 40)),
)
walking: Action | None = None
hero = Sprite(idle, x=-300, y=-150, scale=1.5, layer=2)
hero.rotation_style = RotationStyle.LEFT_RIGHT
stage.add(hero)
sentry = Costume(assets / "robot.png", anchor=(16, 40))
friendly_shot = Costume(assets / "friendly_shot.png")
hostile_shot = Costume(assets / "hostile_shot.png")
enemies: list[Sprite] = []
# A shot stores (sprite, sideways speed, friendly). True means the hero fired it.
shots: list[tuple[Sprite, float, bool]] = []
vertical_speed = 0.0
next_shot = 0.0
protected_until = 0.0
health = 3
defeated = 0


def finished() -> bool:
    return health <= 0 or (not enemies and hero.x >= 1680)


def grounded() -> bool:
    """Are the hero's feet resting on the ground or a platform?"""
    if vertical_speed > 0:
        return False
    surfaces = [ground.bounds]
    for platform in platforms:
        surfaces.append(platform.bounds)
    for surface in surfaces:
        feet_at_top = abs(hero.y - surface.top) < 0.01
        overlaps_sideways = hero.bounds.right > surface.left and hero.bounds.left < surface.right
        if feet_at_top and overlaps_sideways:
            return True
    return False


def fire(actor: Sprite, friendly: bool) -> None:
    """Make a bullet. The hero aims forward; robots aim toward the hero."""
    direction = 1
    if friendly:
        costume = friendly_shot
        speed = 560
        if actor.direction != 90:
            direction = -1
    else:
        costume = hostile_shot
        speed = 230
        if hero.x <= actor.x:
            direction = -1
    shot = Sprite(
        costume,
        x=actor.x + direction * 30,
        y=actor.y + 32,
        layer=3,
    )
    stage.add(shot)
    shots.append((shot, direction * speed, friendly))


def spawn_enemies() -> None:
    for x, y in ((140, -150), (440, -22), (730, -150), (970, -86), (1260, -150), (1490, -86)):
        enemy = Sprite(sentry, x=x, y=y, scale=1.5, layer=1)
        enemy.rotation_style = RotationStyle.LEFT_RIGHT
        stage.add(enemy)
        enemies.append(enemy)

        # The default actor=enemy remembers THIS robot, even after the loop moves on.
        def fire_when_near(actor: Sprite = enemy) -> None:
            if not finished() and abs(actor.x - hero.x) < 480:
                actor.direction = 90
                if hero.x <= actor.x:
                    actor.direction = 270
                fire(actor, False)

        # Each robot walks and fires at the same time using two repeating recipes.
        patrol = enemy.repeat()
        patrol.glide_to(x=x + 45, seconds=1.2)
        patrol.glide_to(x=x, seconds=1.2)
        firing = enemy.repeat()
        firing.wait(1.5)
        firing.call(fire_when_near)
        enemy.during(patrol, meanwhile=firing)


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


# @ connects a function to a key press. Holding X is checked in update instead.
@stage.on_key_down(Key.SPACE)
def jump() -> None:
    # global lets this helper change the jump speed at the top of this file.
    global vertical_speed
    if not finished() and grounded():
        vertical_speed = 650


@stage.on_key_down(Key.R)
def restart() -> None:
    global health, defeated, vertical_speed, next_shot, protected_until
    hero.stop()
    for enemy in enemies:
        stage.remove(enemy)
    enemies.clear()
    # A copy lets us remove bullets without skipping the next one in the list.
    for shot in shots.copy():
        remove_shot(shot)
    hero.position = (-300, -150)
    hero.direction = 90
    hero.costume = idle
    hero.visible = True
    vertical_speed = 0
    health = 3
    defeated = 0
    next_shot = stage.time
    protected_until = stage.time + 1
    stage.camera = (0, 0)
    spawn_enemies()


@stage.on_key_down(Key.P)
def toggle_pause() -> None:
    if stage.paused:
        stage.resume()
    else:
        stage.pause()


# dt is the time since the last game step. Speed × dt gives the distance to move.
@stage.on_update
def update(dt: float) -> None:
    global vertical_speed, next_shot, defeated, walking
    if finished():
        if walking is not None:
            walking.cancel()
        hero.costume = idle
        hero.visible = True
        return
    direction = 0
    if stage.keyboard.is_down(Key.RIGHT):
        direction += 1
    if stage.keyboard.is_down(Key.LEFT):
        direction -= 1
    hero.x = max(-365, min(1770, hero.x + direction * 220 * dt))
    if direction > 0:
        hero.direction = 90
    elif direction < 0:
        hero.direction = 270
    if direction and grounded():
        if walking is None or walking.done:
            walking = hero.act(hero.repeat().costumes(walking_frames, fps=9))
    else:
        if walking is not None:
            walking.cancel()
        hero.costume = idle

    previous_feet = hero.y
    vertical_speed -= 1500 * dt
    hero.y += vertical_speed * dt
    # Land only while falling across a platform's top. This lets us jump through below.
    surfaces = [ground.bounds]
    for platform in platforms:
        surfaces.append(platform.bounds)
    landings: list[float] = []
    for surface in surfaces:
        crossed_top = previous_feet >= surface.top >= hero.y
        overlaps_sideways = hero.bounds.right > surface.left and hero.bounds.left < surface.right
        if vertical_speed <= 0 and crossed_top and overlaps_sideways:
            landings.append(surface.top)
    if landings:
        hero.y = max(landings)
        vertical_speed = 0
    # Blink during the safe moment after a hit. % 2 alternates between zero and one.
    hero.visible = stage.time >= protected_until or int(stage.time * 12) % 2 == 0
    if stage.keyboard.is_down(Key.X) and stage.time >= next_shot:
        fire(hero, True)
        next_shot = stage.time + 0.16

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
    stage.camera = (max(0, min(1400, hero.x - 60)), 0)
    backdrop.offset = (-stage.camera[0] * 0.22, 0)


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
