"""Railgun Range: instant ray hits, bright beams, and ordinary physical bumps."""

from pathlib import Path

from plocks import (
    Anchor,
    BodyType,
    Bounds,
    Collision,
    Effect,
    Event,
    GamepadButton,
    GamepadPress,
    Image,
    Key,
    Label,
    RotationStyle,
    Sound,
    Sprite,
    Stage,
    TileMap,
    distance,
)

assets = Path(__file__).resolve().parent / "assets"
stage = Stage(width=800, height=450, physics=True, background="#102735")
player = stage.gamepads[0]
player.map_left_stick(left=Key.LEFT, right=Key.RIGHT)
player.map_key(Key.X, GamepadButton.B)
player.map_key(Key.R, GamepadButton.SELECT)

# Solid tiles and robots stay in the world. The camera follows our hero.
floor = TileMap(
    ["#" * 40] * 2,
    {"#": assets / "ground.png"},
    tile_size=(32, 32),
    solid={"#"},
    x=-400,
    y=-150,
    layer=-2,
)
cover = TileMap(
    ["#......#......#"] * 2,
    {"#": assets / "ground.png"},
    tile_size=(32, 32),
    solid={"#"},
    x=-64,
    y=-86,
    layer=-1,
)
stage.add(floor)
stage.add(cover)
hero = Sprite(Image(assets / "hero.png").resized(40, 56), x=-280, y=-122)
stage.add(hero)
hero.body.rotation_locked = True
hero.body.friction = 0
hero.rotation_style = RotationStyle.LEFT_RIGHT
stage.follow(hero, bounds=Bounds(-400, -225, 880, 225), offset=(-60, 0))

targets: list[Sprite] = []
for x in (60, 300, 600):
    target = Sprite(
        Image(assets / "robot.png").resized(48, 56), x=x, y=-122, body_type=BodyType.STATIC
    )
    stage.add(target)
    targets.append(target)

zap = Sound(assets / "pop.ogg")
shots = 0
hits = 0
score = Label("Robots: 0 / 3    Shots: 0", position=(0, 200), size=24)
status = Label("Blast the top bricks, then jump over the low ones.", position=(0, 168), size=19)
stage.add(score)
stage.add(status)
stage.add(Label("Arrows: walk   Space: jump   X: railgun   R: reset", position=(0, -205), size=19))


@hero.on_button_down(GamepadButton.B, gamepad=player, repeat=0.3)
def fire(event: Event[Sprite, GamepadPress]) -> None:
    global shots, hits
    actor = event.target
    facing = 1 if actor.direction == 90 else -1
    start = (actor.x + facing * 26, actor.y + 8)
    end = (start[0] + facing * 900, start[1])
    hit = stage.physics.raycast(start, end, ignore=(actor,))
    shots += 1

    # A ray finds the first target immediately. We choose the damage here.
    if hit is not None:
        end = hit.point
        if hit.target is cover and hit.cell is not None:
            row, column = hit.cell
            cover.set_tile(row=row, column=column, tile=None)
            status.text = "Brick blasted!"
        elif isinstance(hit.target, Sprite) and hit.target in targets:
            hit.target.remove()
            hits += 1
            status.text = "Robot zapped!" if hits < 3 else "All robots cleared! Press R to replay."

    # Pictures show the blast. They have no body and disappear after a short flash.
    length = max(1, round(distance(start, end)))
    for thickness, color, seconds in (
        (12, "#145aab", 0.16),
        (4, "#a5f3fc", 0.10),
        (2, "white", 0.07),
    ):
        image = Image.rectangle(length, thickness, color=color).with_anchor(Anchor.CENTER_LEFT)
        beam = Sprite(
            image,
            x=start[0],
            y=start[1],
            direction=actor.direction,
            body_type=BodyType.NONE,
            layer=100,
        )
        stage.add(beam)
        beam.remove_after(seconds=seconds)
    stage.play(zap, volume=0.25)
    score.text = f"Robots: {hits} / 3    Shots: {shots}"


@hero.on_hit
def bump(event: Event[Sprite, Collision]) -> None:
    # Real body contact is separate from the railgun's read-only ray query.
    other = event.data.target
    if other is cover or other in targets:
        event.target.act(
            event.target.sequence()
            .animate_effect(Effect.BRIGHTNESS, to=60, seconds=0.05)
            .animate_effect(Effect.BRIGHTNESS, to=0, seconds=0.2)
        )
    if other is cover:
        status.text = "Wall contact! Blast a brick or jump."
    elif other in targets:
        status.text = "Robot contact! Step back and fire."


@hero.on_button_down(GamepadButton.A, gamepad=player)
def jump(event: Event[Sprite, GamepadPress]) -> None:
    event.target.body.jump(height=108)


@hero.on_update
def walk(event: Event[Sprite, float]) -> None:
    actor = event.target
    speed = player.left_stick[0] * 170
    if speed:
        actor.direction = 90 if speed > 0 else 270
    actor.body.walk(speed=speed)
    if actor.y < -300:
        actor.position = (-280, -122)
        actor.body.velocity = (0, 0)


@stage.on_button_down(GamepadButton.SELECT, gamepad=player)
def reset(event: Event[Stage, GamepadPress]) -> None:
    global shots, hits
    shots = hits = 0
    for target in targets:
        if target not in stage.objects:
            stage.add(target)
    for row in (0, 1):
        for column in (0, 7, 14):
            cover.set_tile(row=row, column=column, tile="#")
    hero.position = (-280, -122)
    hero.direction = 90
    hero.body.velocity = (0, 0)
    score.text = "Robots: 0 / 3    Shots: 0"
    status.text = "Blast the top bricks, then jump over the low ones."


if __name__ == "__main__":
    stage.run()
