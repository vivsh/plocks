# Make a movement script

[Home](../index.md) · [More activities](index.md)

**Goal:** make your dinosaur patrol, and hop when you press Space.

1. [Download Dino Dash](../dino-run/assets.md) and unzip it.
2. Save this as `movement.py` inside its `dino_run` folder.
3. Run `python movement.py`. Press Space while the dinosaur moves sideways!

```python
from pathlib import Path

from plocks import Image, Ease, GamepadButton, Sprite, Stage

assets = Path(__file__).resolve().parent / "assets"
stage = Stage(background="skyblue")
hero = Sprite(Image(assets / "dinosaur.png").resized(width=72, height=72), x=-100)
stage.add(hero)

# Repeat the whole trip three times.
patrol = hero.repeat(3)
patrol.glide_by(x=200, seconds=2)
patrol.wait(0.5)
patrol.glide_by(x=-200, seconds=2)
hero.on_start(patrol)

# A second script moves only up and down.
hop = hero.sequence()
hop.glide_by(y=80, seconds=0.3, easing=Ease.OUT)
hop.glide_by(y=-80, seconds=0.3, easing=Ease.IN)
hero.on_button_down(GamepadButton.A, hop, gamepad=stage.gamepads[0])

if __name__ == "__main__":
    stage.run()
```

A **script** is a list of jobs for your character. The jobs run in order.
Recording one does not start it: `on_start` or a key press does.
Our patrol changes x and the hop changes y, so both can happen together.
Extra Space presses are ignored until the hop finishes.

## Connect two commands with after

You can also write these lines inside a named event function:

```python
up = hero.glide_by(y=80, seconds=0.3)
hero.glide_by(y=-80, seconds=0.3, after=up)
```

`after=up` makes the second move wait. Without it, the two calls try to start together.
`hero.stop()` stops that character's work; it does not move the character back home.

**Make it yours:** change `repeat(3)` to `repeat()` for a never-ending patrol.
For jumping onto real ground, try [jumping and landing](physics.md).
