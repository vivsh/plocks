# Give a character a memory 🪙

[Home](../index.md) · [More activities](index.md)

**Goal:** give two dinosaurs their own coin counts.

1. [Download Dino Dash](../dino-run/assets.md) and unzip it.
2. Save this as `memory.py` inside its `dino_run` folder.
3. Run `python memory.py`. Press Space, then Enter. Watch each coin count!

```python
from dataclasses import dataclass
from pathlib import Path

from plocks import Costume, Event, GamepadButton, Sprite, Stage, GamepadPress


@dataclass
class Memory:
    coins: int = 0


assets = Path(__file__).resolve().parent / "assets"
stage = Stage(background="skyblue")
picture = Costume(assets / "dinosaur.png").resized(width=72, height=72)
hero = Sprite(picture, x=-100, state=Memory)
friend = Sprite(picture, x=100, state=Memory)
stage.add(hero)
stage.add(friend)


@hero.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])
@friend.on_button_down(GamepadButton.A, gamepad=stage.gamepads[1])
def collect(event: Event[Sprite[Memory], GamepadPress]) -> None:
    event.target.state.coins += 1
    event.target.say(f"Coins: {event.target.state.coins}", seconds=1)


if __name__ == "__main__":
    stage.run()
```

`Memory` is a **dataclass**: a little bundle of named values.
`coins: int = 0` starts a whole-number count at zero.
Passing `state=Memory` gives each character a fresh bundle.

`event.target` is the character whose key you pressed. `+= 1` adds one coin.
The f-string puts that character's current count into its speech bubble.
For memory the whole game shares, give the Stage its own dataclass with `state=`.

**Make it yours:** add `gems: int = 0` beneath `coins` in Memory. Change the
function to add gems instead. Hover over `event.target.state` to see your editor's hints.

Want one character to reward another? [Try the messages lab](../dino-run/06-more-plocks.md#give-coins-to-two-players).
