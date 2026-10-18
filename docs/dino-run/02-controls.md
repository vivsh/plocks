# 2. Take control

[Home](../index.md) · [Dino Dash course](index.md)

**Goal:** walk with held arrow keys and hop with Space.

1. Run [02_controls.py](../../src/plocks/_games/dino_run/02_controls.py).
2. Hold Left or Right. Tap Space.
3. Change `160` to `220` and try again.

## Where is the dinosaur?

The middle of the stage is `(0, 0)`. **x** goes right; **y** goes up.
A position such as `(-100, 40)` is a tuple: two values kept together.

```python
@dino.on_update
def walk(event: Event[Sprite, float]) -> None:
    if stage.gamepads[0].left_stick[0] > 0:
        event.target.x += 160 * event.data
```

`def` gives a job a name. The `@` line connects that job to an event.
`on_update` runs once per game step. `event.target` is our dinosaur;
`event.data` is the step's time in seconds. **Speed × time = distance.**
`+=` adds to the old value.

`Event[Sprite, float]` tells the editor what the function receives. `-> None`
means the function gives back no value. You do not need to create Events yourself.
`event.source` tells you who caused an event; for an update, that is the stage.

## One press or held down?

`on_button_down` fires once when a button is pressed. Read the stick for walking.
Optional `repeat=0.2` repeats a button handler while held, but jumps usually need one press.

Our `hop = dino.sequence()` records two moves. `dino.on_button_down(GamepadButton.A, hop, gamepad=stage.gamepads[0])`
plays the script. More presses are ignored while that hop is busy.
`Ease.OUT` slows the rise; `Ease.IN` speeds up the fall.

Another way to connect two commands is `after`:

```python
up = dino.glide_by(y=90, seconds=0.3)
dino.glide_by(y=-90, seconds=0.3, after=up)
```

Put those lines inside a named button handler if you try them. Commands schedule work;
`after` makes the second wait for the first. Scripts wait in their recorded order.
Properties such as `dino.x = 0` change immediately.

This hop is an authored path. Next we will use physics to land on real ground.

[Next: jump and land →](03-jump-and-scroll.md)
