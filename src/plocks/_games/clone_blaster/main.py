"""Clone Blaster: press gamepad B (or X) to fire reusable bullet copies."""

from pathlib import Path

from plocks import (
    Anchor,
    BodyType,
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
hero.rotation_style = RotationStyle.LEFT_RIGHT

# Keep one hidden bullet attached as our template. clone() adds each copy itself.
# A kinematic sensor flies without gravity and does not push the targets.
bullet = Sprite(
    Image(assets / "friendly_shot.png").resized(16, 8), y=1000, body_type=BodyType.KINEMATIC
)
bullet.visible = False
stage.add(bullet)
bullet.body.sensor = True

robots: list[Sprite] = []
for x in (40, 170, 290):
    robot = Sprite(
        Image(assets / "robot.png").resized(48, 56).with_anchor(Anchor.BOTTOM_CENTER),
        x=x,
        y=-144,
        body_type=BodyType.STATIC,
    )
    stage.add(robot)
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
    if sum(isinstance(obj, Sprite) and obj.is_clone for obj in stage.objects) >= 16:
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
    if event.target.body.grounded:
        event.target.body.impulse(y=420)


@hero.on_update
def walk(event: Event[Sprite, float]) -> None:
    actor = event.target
    speed = player.left_stick[0] * 170
    if speed:
        actor.direction = 90 if speed > 0 else 270
        # Check this tick's horizontal step before walking into a wall.
        if not actor.body.can_travel(distance=abs(speed) * event.data):
            speed = 0
    actor.body.velocity = (speed, actor.body.velocity[1])


@bullet.on_touch(world)
def hit_wall(event: Event[Sprite, TileMap]) -> None:
    bullet_clone = event.target
    if bullet_clone.is_clone:
        bullet_clone.remove()


def hit_robot(event: Event[Sprite, Sprite]) -> None:
    global hits
    bullet_clone = event.target
    if bullet_clone.is_clone:
        # Remove this copy, never the hidden template. Later shots still clone it.
        bullet_clone.remove()
        hits += 1
        show_score()


for target in robots:
    bullet.on_touch(target)(hit_robot)


@bullet.on_update
def clean_up(event: Event[Sprite, float]) -> None:
    bullet_clone = event.target
    # Hidden actors also receive updates. Leave the original template attached!
    if bullet_clone.is_clone and not stage.world_bounds.intersects(bullet_clone.bounds):
        bullet_clone.remove()


if __name__ == "__main__":
    stage.run()
