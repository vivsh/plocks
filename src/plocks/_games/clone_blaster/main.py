"""Clone Blaster: press gamepad B (or X) to fire reusable bullet copies."""

from pathlib import Path

from plocks import (
    Anchor,
    BodyType,
    Collision,
    Event,
    GamepadButton,
    GamepadPress,
    Image,
    Key,
    Label,
    RotationStyle,
    Sprite,
    Stage,
    TileMap,
)

assets = Path(__file__).resolve().parent / "assets"
stage = Stage(width=800, height=450, physics=True, background="#102735")
player = stage.gamepads[0]
player.map_left_stick(left=Key.LEFT, right=Key.RIGHT)
player.map_key(Key.X, GamepadButton.B)

# The outside columns make walls. The last row makes the floor.
world = TileMap(
    ["#" + "." * 23 + "#"] * 10 + ["#" * 25],
    {"#": assets / "ground.png"},
    tile_size=(32, 32),
    solid={"#"},
    x=-400,
    y=176,
    layer=-1,
)
stage.add(world)
hero = Sprite(Image(assets / "hero.png").resized(40, 56), x=-260, y=-116)
stage.add(hero)
hero.body.rotation_locked = True
# Keep the hero in the level, even while a movement control stays held.
hero.keep_inside(world.bounds)
hero.rotation_style = RotationStyle.LEFT_RIGHT
hero.body.collision_group = "player"

# Keep one hidden bullet attached as our template. clone() adds each copy itself.
# A kinematic sensor flies without gravity and does not push the targets.
bullet = Sprite(
    Image(assets / "friendly_shot.png").resized(16, 8), y=1000, body_type=BodyType.KINEMATIC
)
bullet.visible = False
stage.add(bullet)
# Swept bullets stop at thin walls too. Friendly shots pass through the hero.
bullet.body.projectile = True
bullet.body.collision_group = "player-shot"
bullet.body.collides_with = {"enemy", "terrain"}

robots: list[Sprite] = []
for x in (40, 170, 290):
    robot = Sprite(
        Image(assets / "robot.png").resized(48, 56).with_anchor(Anchor.BOTTOM_CENTER),
        x=x,
        y=-144,
        body_type=BodyType.STATIC,
    )
    stage.add(robot)
    robot.body.collision_group = "enemy"
    robots.append(robot)

shots = 0
hits = 0
score = Label("Shots: 0    Hits: 0", position=(0, 192), size=26)
stage.add(score)
stage.add(Label("Arrows: walk    Space: jump    X / gamepad B: fire", position=(0, -205), size=20))


def show_score() -> None:
    score.text = f"Shots: {shots}    Hits: {hits}"


@hero.on_button_down(GamepadButton.B, gamepad=player, repeat=0.18)
def fire(event: Event[Sprite, GamepadPress]) -> None:
    global shots
    # This handler belongs to the hero, so bullet copies never inherit it.
    # Limit live copies; count the scene instead of keeping another bullet list.
    if bullet.clone_count >= 16:
        return
    bullet_clone = bullet.clone()
    bullet_clone.visible = True
    speed = 520 if event.target.direction == 90 else -520
    bullet_clone.position = (event.target.x + (30 if speed > 0 else -30), event.target.y + 4)
    bullet_clone.body.travel_along(speed=520, direction=event.target.direction)
    shots += 1
    show_score()


@hero.on_button_down(GamepadButton.A, gamepad=player)
def jump(event: Event[Sprite, GamepadPress]) -> None:
    event.target.body.jump(height=98)


@hero.on_update
def walk(event: Event[Sprite, float]) -> None:
    actor = event.target
    speed = player.left_stick[0] * 170
    if speed:
        actor.direction = 90 if speed > 0 else 270
        # Check this tick's horizontal step before walking into a wall.
        if not actor.body.can_travel(distance=abs(speed) * event.data):
            speed = 0
    actor.body.walk(speed=speed)


@bullet.on_clone_start
def start_bullet(event: Event[Sprite, None]) -> None:
    # Even a missed copy disappears after two game seconds.
    event.target.remove_after(seconds=2)


@bullet.on_hit
def hit(event: Event[Sprite, Collision]) -> None:
    global hits
    bullet_clone = event.target
    if bullet_clone.is_clone:
        # Hit data names the wall or robot. Remove only this receiving copy.
        if event.data.target in robots:
            hits += 1
            show_score()
        bullet_clone.remove()


if __name__ == "__main__":
    stage.run()
