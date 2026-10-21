"""Maze Quest: click a route, collect coins, and watch out for the patrolling robot."""

from dataclasses import dataclass
from pathlib import Path

from plocks import (
    Button,
    Click,
    Event,
    GamepadButton,
    GamepadPress,
    Image,
    Key,
    Label,
    MouseButton,
    ProgressBar,
    Sound,
    Sprite,
    Stage,
    TileMap,
)


@dataclass
class Game:
    coins: int = 0
    health: float = 100


# Pictures stay beside this file, so your copied game runs from any folder.
assets = Path(__file__).resolve().parent / "assets"
stage = Stage(width=640, height=400, background="#172536", state=Game)
player = stage.gamepads[0]
player.map_key(Key.P, GamepadButton.START)
world = TileMap(
    [
        "#################",
        "#.....#.........#",
        "#.###.#.#####.#.#",
        "#.#...#.....#.#.#",
        "#.#.#######.#.#.#",
        "#.#.........#...#",
        "#.###########.#.#",
        "#.............#.#",
        "#################",
    ],
    {"#": assets / "wall.png"},
    tile_size=(64, 64),
    solid={"#"},
    x=-544,
    y=288,
)
stage.add(world)
hero = Sprite(Image(assets / "hero.png").resized(24, 28))
spawn = world.cell_center(row=1, column=1)
hero.position = spawn
stage.add(hero)
stage.follow(hero, bounds=world.bounds, smoothing=0.12)
score = Label("Coins: 0 / 4", position=(-225, 172))
health = ProgressBar(value=100, position=(-225, 144), width=150, height=12)
hint = Label("Click a floor tile. P pauses.", position=(0, -177), size=22)
resume = Button("Continue", position=(0, 0))
resume.visible = False
for control in (score, health, hint, resume):
    stage.add(control)
pop = Sound(assets / "pop.ogg")


# This function is reused by all four coin subscriptions. data is that coin.
def collect(event: Event[Sprite, Sprite]) -> None:
    stage.remove(event.data)
    stage.state.coins += 1
    score.text = f"Coins: {stage.state.coins} / 4"
    stage.play(pop)
    if stage.state.coins == 4:
        hint.text = "All four coins! You solved the maze."


for row, column in ((1, 5), (1, 15), (5, 9), (7, 13)):
    coin = Sprite(Image(assets / "coin.png").resized(24, 24))
    coin.position = world.cell_center(row=row, column=column)
    stage.add(coin)
    hero.on_touch(coin)(collect)

spikes = Sprite(Image(assets / "spike.png").resized(28, 24))
spikes.position = world.cell_center(row=3, column=3)
stage.add(spikes)
enemy = Sprite(Image(assets / "enemy.png").resized(26, 26))
enemy.position = world.cell_center(row=7, column=3)
stage.add(enemy)
patrol = enemy.repeat()
patrol.follow_path(
    (world.cell_center(row=7, column=11), world.cell_center(row=7, column=3)), speed=70
)
enemy.on_start(patrol)


# Each new overlap hurts once; staying in contact does not subtract every frame.
def hurt(event: Event[Sprite, Sprite]) -> None:
    stage.state.health = max(0, stage.state.health - 25)
    health.value = stage.state.health
    hero.say("Ouch! Try another route.", seconds=1)
    if stage.state.health == 0:
        hero.stop()
        resume.text = "Try again"
        resume.visible = True
        stage.focus(resume)
        stage.pause()


hero.on_touch(spikes)(hurt)
hero.on_touch(enemy)(hurt)


@stage.on_click
def choose_route(event: Event[Stage, Click]) -> None:
    position, button = event.data
    if stage.paused or button is not MouseButton.LEFT:
        return
    # Clicks are on the screen. Add the camera to find that place in the world.
    point = (position[0] + stage.camera[0], position[1] + stage.camera[1])
    cell = world.cell_at(x=point[0], y=point[1])
    if cell is None:
        return
    goal = world.cell_center(row=cell[0], column=cell[1])
    route = world.find_path(start=hero.position, goal=goal, actor=hero)
    if route is None:
        hero.say("That way is blocked.", seconds=1)
    else:
        hero.follow_path(route, speed=180)


@stage.on_button_down(GamepadButton.START, gamepad=player)
def pause(event: Event[Stage, GamepadPress]) -> None:
    resume.text = "Continue"
    resume.visible = True
    stage.focus(resume)
    stage.pause()


@resume.on_click
def continue_game(event: Event[Button, None]) -> None:
    if stage.state.health == 0:
        stage.state.health = 100
        health.value = 100
        hero.position = spawn
    event.target.visible = False
    stage.resume()


if __name__ == "__main__":
    stage.run()
