# Make copies of a character

[Home](../index.md)

**Goal:** press Space to launch copies. Each copy has its own physics body!

## 1. Make a playground

With Plocks installed, run:

```sh
plocks examples platformer --copy-to clone-game
cd clone-game
```

Keep `assets`, replace `main.py` with the code below, then run `python main.py`.

## 2. Launch a copy

```python
from pathlib import Path

from plocks import Event, GamepadButton, Sprite, Stage, GamepadPress

assets = Path(__file__).resolve().parent / "assets"
stage = Stage(physics=True, background="midnightblue")
stage.physics.gravity = (0, 0)

# Keep our hidden original outside the play area. Copies use its picture and controls.
original = Sprite(assets / "hero.png", x=-1000)
original.visible = False
stage.add(original)


# This runs for each new copy. event.target means that particular copy.
@original.on_clone
def launch(event: Event[Sprite, None]) -> None:
    copy = event.target
    copy.visible = True
    copy.body.velocity = (220, 0)


# Copies inherit this function. Remove each one when it leaves the screen.
@original.on_update
def tidy_up(event: Event[Sprite, float]) -> None:
    copy = event.target
    if copy.is_clone and copy.x > stage.world_bounds.right + 30:
        stage.remove(copy)


# Put the spawning control on the stage, so copies do not spawn more copies!
@stage.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])
def make_copy(event: Event[Stage, GamepadPress]) -> None:
    copy = original.clone()
    copy.position = (-180, 0)


if __name__ == "__main__":
    stage.run()
```

`original.clone()` adds the copy to the stage for you. Change its position straight
away—there is no extra `stage.add(copy)` step.

## 3. Make it yours

- Change `(220, 0)` to `(100, 100)` to launch diagonally.
- Try gravity `(0, -200)` to make copies fall.
- Change each copy's size with `copy.scale = 0.5` inside `launch`.

A copy starts with the original's current picture, size and settings. Its clone-start
function runs later, so you can place it first. Running movement scripts, speech
bubbles and playing sounds are not copied. Puppets support the same clone methods.

**Physics:** shapes and materials are copied into separate bodies. Velocity starts
at zero; your launch function sets it. Copies can collide with each other. Hiding
an actor does not turn off physics—that is why our original stays outside the screen.

**Character memory:** if you add [memory](memory.md), each clone can change its own
health or coin numbers. Lists and dictionaries inside that memory start shared.
For a list named `items`, give a clone its own list with
`copy.state.items = list(copy.state.items)`.

Use `event.target` in inherited functions. Writing `original.x` still changes the
original. Remove unwanted copies with `stage.remove(copy)`; that also clears their
inherited controls and running actions. A stage allows up to 300 attached clones.

## Remove a copy

Use `copy.remove()` when you no longer need a character. It also works for Puppets.
In an inherited handler, use `event.target.remove()` to remove the copy receiving
that event. Removing it stops its scripts and releases its physics body.
Calling `remove()` again is harmless.

Add a character to the stage **before** registering its handlers. Currently,
Plocks stores those registrations on the stage.
