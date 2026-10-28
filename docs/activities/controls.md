# Play with a friend 🎮

[Home](../index.md) · [More activities](index.md)

**Goal:** control two dinosaurs with keys or gamepads.

1. [Download Dino Dash](../dino-run/assets.md) and unzip it.
2. Open a terminal inside its `dino_run` folder.
3. Run `python labs/messages.py`. Click a dinosaur, or use the controls below!

## Two players, ready to go

A **slot** is one player's controls. `stage.gamepads[0]` is player one;
`stage.gamepads[1]` is player two. You can use them without owning a controller.

| Action in the lab | Player 1 | Player 2 |
| --- | --- | --- |
| Move left / right | A / D | Left / Right arrows |
| Button A: collect coins | Space | Enter |
| Button B: available for another action | F | Right Shift |

W/S and Up/Down also control the stick's up/down direction.
The lab moves sideways only. In Dino Dash, Space jumps instead of collecting coins:
your game decides what each button does.

## Hold or tap?

Read `player.left_stick` inside an update function for smooth held movement.
A button handler fires once on a fresh press. Adding `repeat=0.25` makes it repeat
while held, like the lab's coin button. Leave repeat off for a normal jump.

The lab's `turbo` function receives an Event. `event.target` is the dinosaur;
`event.data.gamepad` tells you which player's controls were used. You can check
another button on that same controller without a global variable:

```python
@hero.on_button_down(GamepadButton.X)
def shoot(event: Event[Sprite, GamepadPress]) -> None:
    if event.data.gamepad.is_down(GamepadButton.UP):
        print("Shoot upwards!")
```

To do something once when the player lets go, use `on_button_up`:

```python
@hero.on_button_up(GamepadButton.X)
def stop_shooting(event: Event[Sprite, GamepadRelease]) -> None:
    print("Stopped!")
```

Import `Event`, `Sprite`, `GamepadPress` and `GamepadRelease` from `plocks`.
If two keys control the same button, it is released after both keys are up.

## Make it yours

Player one already has Space for A. Before the final run guard, add:

```python
from plocks import GamepadButton, Key

first.map_key(Key.J, GamepadButton.A)
```

Now J works too! Try the lab's Space and Enter together: both dinosaurs collect coins.

Controllers work through the same slots when your computer recognizes them.
Nintendo and Xbox use different face-button labels. The lab shows how to choose
`GamepadLayout.NINTENDO` for player two. Keyboard keys keep their logical A/B names.

**Stuck?** Click the game window first. The [keyboard works even without a controller](../help/index.md#my-keys-or-controller-do-nothing).
