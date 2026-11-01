"""Tiny tank playground: move between tiles and blast the brick walls."""

from plocks import (
    Action,
    BodyType,
    Collision,
    Event,
    GamepadButton,
    GamepadPress,
    Image,
    Label,
    Sprite,
    Stage,
    TileMap,
)

stage = Stage(width=480, height=360, physics=True, background="#162b36")
stage.physics.gravity = (0, 0)
world = TileMap(
    [
        "###########",
        "#.........#",
        "#..##.##..#",
        "#.........#",
        "#..#...#..#",
        "#.........#",
        "###########",
    ],
    {"#": Image.rectangle(32, 32, color="#b65a3b")},
    tile_size=(32, 32),
    solid={"#"},
    x=-176,
    y=112,
)
stage.add(world)

tank = Sprite(Image.rectangle(20, 20, color="#4ec2e8"), body_type=BodyType.KINEMATIC)
tank.position = world.cell_center(row=5, column=2)
stage.add(tank)
tank.body.collision_group = "player"

# A hidden original supplies copies. Projectile mode handles fast impacts.
bullet = Sprite(Image.circle(3, color="#ffdc68"), y=1000, body_type=BodyType.KINEMATIC)
bullet.visible = False
stage.add(bullet)
bullet.body.projectile = True
bullet.body.collides_with = {"terrain"}
heading = {
    GamepadButton.UP: 0,
    GamepadButton.RIGHT: 90,
    GamepadButton.DOWN: 180,
    GamepadButton.LEFT: 270,
}
status = Label("Arrows: drive   Space: fire", position=(0, 145), size=22)
stage.add(status)


@tank.on_button_down(GamepadButton.UP, repeat=0.18)
@tank.on_button_down(GamepadButton.RIGHT, repeat=0.18)
@tank.on_button_down(GamepadButton.DOWN, repeat=0.18)
@tank.on_button_down(GamepadButton.LEFT, repeat=0.18)
def drive(event: Event[Sprite, GamepadPress]) -> Action:
    actor = event.target
    actor.direction = heading[event.data.button]
    return actor.move_cell(world, direction=actor.direction, seconds=0.15)


@tank.on_button_down(GamepadButton.A, repeat=0.2)
def fire(event: Event[Sprite, GamepadPress]) -> None:
    if bullet.clone_count < 4:
        copy = bullet.clone()
        copy.position = event.target.position
        copy.direction = event.target.direction


@bullet.on_clone_start
def launch(event: Event[Sprite, None]) -> None:
    copy = event.target
    copy.visible = True
    copy.body.travel_along(speed=500)
    copy.remove_after(seconds=2)


@bullet.on_hit
def hit(event: Event[Sprite, Collision]) -> None:
    # Tile hits name the exact row and column. None makes that cell empty.
    cell = event.data.cell
    if cell is not None:
        world.set_tile(row=cell[0], column=cell[1], tile=None)
    event.target.remove()


@bullet.on_clone_end
def ended(event: Event[Sprite, None]) -> None:
    status.text = f"Arrows: drive   Space: fire   Bullets: {bullet.clone_count}"


if __name__ == "__main__":
    stage.run()
