# 3. Jump and land

[Home](../index.md) · [Dino Dash course](index.md)

**Goal:** jump, fall, and land without writing a timer.

1. Run [03_jump.py](../../src/plocks/_games/dino_run/03_jump.py).
2. Press Space after the dinosaur settles on the ground.
3. Try changing the jump impulse from `460` to `520`.

## Let gravity do the work

`Stage(physics=True)` turns on physics. A normal Sprite becomes a moving physical
body. Gravity pulls it down. Solid tiles stop it falling through the floor.

```python
@dino.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])
def jump(event: Event[Sprite, GamepadPress]) -> None:
    if event.target.body.grounded:
        event.target.body.impulse(y=460)
```

`grounded` is true while something supports the feet. It prevents jumping again
in midair. An impulse is a quick push. **Do not add a glide to this physical
jumper:** glides author a path; impulses let physics decide the path.

Our costume anchor is at its feet. `Box(38, 58, center=(6, 34))` is the invisible
collision shape above those feet. `rotation_locked = True` keeps the dinosaur
upright. Transparent picture padding does not need to become a big hit box.

## Make the ground

The checkpoint uses `TileMap(["G" * 27], {"G": sand}, ...)`.
`"G" * 27` repeats a letter 27 times. The dictionary maps G to a sand costume.
`solid={"G"}` makes those cells physical ground.
A TileMap's `x, y` mark its **top-left corner**; y decreases down the rows.

A `TiledBackground` repeats a picture behind the game. Changing its `offset`
scrolls the pattern. The dinosaur stays near the left; the scenery travels past.
In the final game clouds scroll slowly and obstacles move quickly, giving depth.

**Make it yours:** change gravity with `stage.physics.gravity = (0, -700)` after
creating the stage. Lower gravity gives floatier jumps.
Try [a bigger jump or floatier gravity](../activities/physics.md).

[Next: add a challenge →](04-obstacles-and-score.md)
