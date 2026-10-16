"""A short run-and-gun level. Arrows move, Space jumps, X fires, R restarts.

All artwork is generated with Pillow. Platforms are one-way: jump through them
from below and land on top. This intermediate example authors its own gravity,
landing and projectiles; Plocks supplies sprites, actions, input and rendering.
"""

from math import sin

from PIL import Image, ImageDraw

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


def soldier(step: int = 0) -> Costume:
    """Draw a right-facing commando with a feet anchor and two running poses."""
    image = Image.new("RGBA", (32, 40))
    pen = ImageDraw.Draw(image)
    pen.rectangle((9, 2, 19, 12), fill="#f2bd86")
    pen.rectangle((7, 1, 20, 5), fill="#ee685b")
    pen.rectangle((18, 7, 20, 8), fill="#162c39")
    pen.rectangle((8, 13, 20, 26), fill="#46c5b6")
    pen.rectangle((10, 15, 17, 25), fill="#16736e")
    pen.rectangle((8, 23, 20, 27), fill="#d8b66b")
    pen.rectangle((17, 16, 27, 20), fill="#f2bd86")
    pen.rectangle((20, 15, 31, 18), fill="#d8e7d5")
    pen.rectangle((23, 18, 26, 23), fill="#354f5d")
    for x, shift in ((8, step * 3), (16, -step * 3)):
        pen.rectangle((x + shift, 28, x + shift + 5, 36), fill="#326984")
        pen.rectangle((x + shift, 36, x + shift + 7, 39), fill="#112333")
    return Costume(image, anchor=(14, 40))


def robot() -> Costume:
    """Draw an original sentry robot, facing left, anchored at its feet."""
    image = Image.new("RGBA", (32, 40))
    pen = ImageDraw.Draw(image)
    pen.rectangle((8, 2, 24, 13), fill="#be5965")
    pen.rectangle((8, 6, 20, 9), fill="#ffcc74")
    pen.rectangle((7, 15, 25, 28), fill="#7f384e")
    pen.rectangle((12, 17, 20, 23), fill="#df7784")
    pen.rectangle((0, 17, 14, 21), fill="#c6d6c7")
    for x in (8, 20):
        pen.rectangle((x, 29, x + 4, 36), fill="#5a4156")
        pen.rectangle((x - 2, 37, x + 5, 39), fill="#d6998b")
    return Costume(image.transpose(Image.Transpose.FLIP_LEFT_RIGHT), anchor=(16, 40))


def jungle() -> Image.Image:
    """Generate a repeating, layered jungle silhouette in screen coordinates."""
    image = Image.new("RGBA", (256, 450), "#102735")
    pen = ImageDraw.Draw(image)
    for y in range(450):
        pen.line((0, y, 255, y), fill=(16, 39 + y // 20, 53 + y // 30))
    for x, height in ((12, 145), (62, 190), (120, 125), (190, 175), (242, 140)):
        pen.rectangle((x, height, x + 8, 449), fill="#193f43")
        for y in range(height, 350, 55):
            pen.polygon(((x + 4, y - 35), (x - 35, y + 40), (x + 42, y + 40)), fill="#1b4948")
    return image


def ledge(width: int) -> Costume:
    """Generate a metal platform; its anchor is its top-left corner."""
    image = Image.new("RGBA", (width, 16), "#334f58")
    pen = ImageDraw.Draw(image)
    pen.rectangle((0, 0, width - 1, 3), fill="#89c79f")
    for x in range(4, width, 24):
        pen.line((x, 6, x + 8, 13), fill="#d0ad6c", width=3)
    return Costume(image, anchor=(0, 0))


def main() -> None:
    """Run one short level with authored platforming, combat and restart logic."""
    stage = Stage(width=800, height=450, background="#102735")
    backdrop = TiledBackground(jungle())
    stage.add(backdrop)

    earth = Image.new("RGBA", (32, 32), "#304044")
    earth_pen = ImageDraw.Draw(earth)
    earth_pen.rectangle((0, 0, 31, 4), fill="#77ac70")
    earth_pen.line((0, 5, 31, 5), fill="#a3cf81")
    earth_pen.rectangle((4, 14, 12, 20), fill="#24343c")
    ground = TileMap(
        ["#" * 70] * 3, {"#": earth}, tile_size=(32, 32), solid={"#"}, x=-400, y=-150, layer=-5
    )
    stage.add(ground)

    platforms: list[Sprite] = []
    for x, y, width in ((100, -86, 160), (390, -22, 160), (910, -86, 170), (1450, -86, 150)):
        platform = Sprite(ledge(width), x=x, y=y, layer=-2)
        platforms.append(platform)
        stage.add(platform)

    flag_image = Image.new("RGBA", (36, 100))
    flag_pen = ImageDraw.Draw(flag_image)
    flag_pen.rectangle((3, 0, 5, 99), fill="#b6d7bd")
    flag_pen.polygon(((6, 1), (33, 1), (26, 14), (33, 27), (6, 27)), fill="#edc46e")
    stage.add(Sprite(Costume(flag_image, anchor=(4, 100)), x=1720, y=-150, layer=-1))

    idle = soldier()
    walking_frames = (soldier(1), soldier(-1))
    walking: Action | None = None
    hero = Sprite(idle, x=-300, y=-150, scale=1.5, layer=2)
    hero.rotation_style = RotationStyle.LEFT_RIGHT
    stage.add(hero)
    sentry = robot()
    friendly_shot = Costume(Image.new("RGBA", (12, 4), "#ffe7a1"))
    hostile_shot = Costume(Image.new("RGBA", (10, 6), "#ff7c81"))
    enemies: list[Sprite] = []
    shots: list[tuple[Sprite, float, bool]] = []
    vertical_speed = 0.0
    next_shot = 0.0
    protected_until = 0.0
    health = 3
    defeated = 0

    def finished() -> bool:
        return health <= 0 or (not enemies and hero.x >= 1680)

    def grounded() -> bool:
        surfaces = (ground.bounds, *(platform.bounds for platform in platforms))
        return vertical_speed <= 0 and any(
            abs(hero.y - surface.top) < 0.01
            and hero.bounds.right > surface.left
            and hero.bounds.left < surface.right
            for surface in surfaces
        )

    def fire(actor: Sprite, friendly: bool) -> None:
        direction = (
            (1 if actor.direction == 90 else -1) if friendly else (1 if hero.x > actor.x else -1)
        )
        shot = Sprite(
            friendly_shot if friendly else hostile_shot,
            x=actor.x + direction * 30,
            y=actor.y + 32,
            layer=3,
        )
        stage.add(shot)
        shots.append((shot, direction * (560 if friendly else 230), friendly))

    def spawn_enemies() -> None:
        for x, y in ((140, -150), (440, -22), (730, -150), (970, -86), (1260, -150), (1490, -86)):
            enemy = Sprite(sentry, x=x, y=y, scale=1.5, layer=1)
            enemy.rotation_style = RotationStyle.LEFT_RIGHT
            stage.add(enemy)
            enemies.append(enemy)

            def fire_when_near(actor: Sprite = enemy) -> None:
                if not finished() and abs(actor.x - hero.x) < 480:
                    actor.direction = 90 if hero.x > actor.x else 270
                    fire(actor, False)

            patrol = enemy.repeat().glide_to(x=x + 45, seconds=1.2).glide_to(x=x, seconds=1.2)
            firing = enemy.repeat().wait(1.5).call(fire_when_near)
            enemy.during(patrol, meanwhile=firing)

    def remove_shot(shot: tuple[Sprite, float, bool]) -> None:
        shots.remove(shot)
        stage.remove(shot[0])

    def hurt() -> None:
        nonlocal health, protected_until
        if stage.time < protected_until or health <= 0:
            return
        health -= 1
        protected_until = stage.time + 1.3
        if health == 0:
            hero.stop()
            for enemy in enemies:
                enemy.stop()

    @stage.on_key_down(Key.SPACE)
    def jump() -> None:
        nonlocal vertical_speed
        if not finished() and grounded():
            vertical_speed = 650

    @stage.on_key_down(Key.R)
    def restart() -> None:
        nonlocal health, defeated, vertical_speed, next_shot, protected_until
        hero.stop()
        for enemy in enemies:
            stage.remove(enemy)
        enemies.clear()
        for shot in tuple(shots):
            remove_shot(shot)
        hero.position = (-300, -150)
        hero.direction = 90
        hero.costume = idle
        hero.visible = True
        vertical_speed = 0
        health, defeated = 3, 0
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

    @stage.on_update
    def update(dt: float) -> None:
        nonlocal vertical_speed, next_shot, defeated, walking
        if finished():
            if walking is not None:
                walking.cancel()
            hero.costume = idle
            hero.visible = True
            return
        direction = int(stage.keyboard.is_down(Key.RIGHT)) - int(stage.keyboard.is_down(Key.LEFT))
        hero.x = max(-365, min(1770, hero.x + direction * 220 * dt))
        if direction:
            hero.direction = 90 if direction > 0 else 270
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
        surfaces = (ground.bounds, *(platform.bounds for platform in platforms))
        landings = [
            surface.top
            for surface in surfaces
            if vertical_speed <= 0
            and previous_feet >= surface.top >= hero.y
            and hero.bounds.right > surface.left
            and hero.bounds.left < surface.right
        ]
        if landings:
            hero.y = max(landings)
            vertical_speed = 0
        hero.visible = stage.time >= protected_until or int(stage.time * 12) % 2 == 0
        if stage.keyboard.is_down(Key.X) and stage.time >= next_shot:
            fire(hero, True)
            next_shot = stage.time + 0.16

        for shot in tuple(shots):
            sprite, speed, friendly = shot
            previous = sprite.bounds
            sprite.x += speed * dt
            current = sprite.bounds
            swept = Bounds(
                min(previous.left, current.left),
                current.bottom,
                max(previous.right, current.right),
                current.top,
            )
            if abs(sprite.x - hero.x) > 650 or any(swept.intersects(p.bounds) for p in platforms):
                remove_shot(shot)
                continue
            if friendly:
                target = next((enemy for enemy in enemies if swept.intersects(enemy.bounds)), None)
                if target is not None:
                    stage.remove(target)
                    enemies.remove(target)
                    defeated += 1
                    remove_shot(shot)
            elif swept.intersects(hero.bounds):
                remove_shot(shot)
                hurt()
        if any(hero.touching(enemy) for enemy in enemies):
            hurt()
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
            title = (
                "MISSION CLEAR!"
                if health > 0 and finished()
                else "TRY AGAIN"
                if health <= 0
                else "PAUSED"
            )
            canvas.text(title, (-110, 40), size=34, color="#edc46e")
            canvas.text(
                "Press R to restart" if finished() else "Press P to continue", (-105, -5), size=23
            )
        else:
            # A pulsing light marks the extraction point ahead.
            goal_x = 1720 - stage.camera[0]
            if -390 < goal_x < 390:
                canvas.circle((goal_x, -42), 3 + sin(stage.time * 4), color="#edc46e")

    spawn_enemies()
    stage.run()


if __name__ == "__main__":
    main()
