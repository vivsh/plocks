"""Typed memory, broadcasts, clicks, two players and turbo controls."""

from dataclasses import dataclass
from pathlib import Path

from plocks import (
    Canvas,
    Click,
    Event,
    GamepadButton,
    GamepadLayout,
    GamepadPress,
    Image,
    Message,
    Sprite,
    Stage,
)


@dataclass
class PlayerMemory:
    coins: int = 0


assets = Path(__file__).resolve().parents[1] / "assets"
stage = Stage(width=640, height=360, background="#fff0cc")
image = Image(assets / "dinosaur.png").resized(width=72, height=72)
one = Sprite(image, x=-130, state=PlayerMemory)
two = Sprite(image.flipped(horizontal=True), x=130, state=PlayerMemory)
stage.add(one)
stage.add(two)
first, second = stage.gamepads[:2]
second.layout = GamepadLayout.NINTENDO
reward = Message[int]("reward")


@one.on_broadcast(reward)
@two.on_broadcast(reward)
def collect(event: Event[Sprite[PlayerMemory], int]) -> None:
    event.target.state.coins += event.data
    event.target.say(f"Coins: {event.target.state.coins}", seconds=0.4)


@one.on_click
@two.on_click
def clicked(event: Event[Sprite[PlayerMemory], Click]) -> None:
    # to limits delivery to this character. Without to, both receive it.
    event.target.broadcast(reward, 1, to=event.target)


@one.on_button_down(GamepadButton.A, gamepad=first, repeat=0.25)
@two.on_button_down(GamepadButton.A, gamepad=second, repeat=0.25)
def turbo(event: Event[Sprite[PlayerMemory], GamepadPress]) -> None:
    event.target.broadcast(reward, 1, to=event.target)


@one.on_update
@two.on_update
def move(event: Event[Sprite[PlayerMemory], float]) -> None:
    gamepad = first if event.target is one else second
    event.target.x += gamepad.left_stick[0] * 100 * event.data


@stage.on_draw
def draw(canvas: Canvas) -> None:
    canvas.text(
        "Click a dino; or hold Space / Enter for coins.", (-300, 150), size=20, color="#24384b"
    )


if __name__ == "__main__":
    stage.run()
