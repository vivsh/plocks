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


## Distance and directional speed

`hero.distance_to(enemy)` measures the straight-line distance between their positions.
You can also use `hero.distance_to((100, 50))` or import `distance` from `plocks`
and call `distance((0, 0), (30, 40))` to get 50 pixels.

`hero.bounds.distance_to(enemy.bounds)` measures the gap between their rectangles.
It returns zero when they touch or overlap. To compare centers, use
`distance(hero.bounds.center, enemy.bounds.center)`.

With physics enabled, set speed along a direction:

```python
hero.body.travel_along(speed=120, direction=90)  # Right, at 120 pixels/second.
hero.body.travel_along(speed=120)               # Use the current facing direction.
hero.body.travel_along(speed=0)                 # Stop moving.
```

Directions are clockwise from up: 0 up, 90 right, 180 down, 270 left.
Turning later does not steer existing velocity. This sets both speed components;
for a platformer, keep the vertical speed when setting sideways `body.velocity`.
