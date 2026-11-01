# Flash, fade and twist!

[Home](../index.md) · [More activities](index.md)

**Goal:** make a walking dinosaur flash or fade while a bird changes color.

1. [Download Dino Dash](../dino-run/assets.md) and unzip it.
2. Save [this program](effects.py) as `effects.py` inside its `dino_run` folder.
3. Run `python effects.py`. **Space** flashes, **X** fades, **C** resets the dinosaur.

## Give your character an effect

```python
from plocks import Effect

hero.set_effect(Effect.GHOST, 50)  # Half transparent.
```

The command runs on the next game step. Changing the picture won't lose the effect.
`Sprite` and `Puppet` both support these effects:

| Effect | Try this | What happens? |
| --- | --- | --- |
| `Effect.COLOR` | `50` | Shift the colors; `200` makes a whole color-wheel turn |
| `Effect.BRIGHTNESS` | `60` | Get brighter; negative amounts get darker |
| `Effect.GHOST` | `50` | Fade halfway; `100` disappears |
| `Effect.PIXELATE` | `40` | Make chunky blocks, about four image pixels wide |
| `Effect.MOSAIC` | `20` | Repeat little copies inside the picture |
| `Effect.WHIRL` | `180` | Twist around the center |
| `Effect.FISHEYE` | `100` | Bulge; try a negative amount to pinch |

Zero restores that effect's ordinary look. Ghost stays between 0 and 100;
brightness stays between -100 and 100. Color goes around and around.

```python
hero.change_effect(Effect.COLOR, by=25)
hero.clear_effects()
```

These are separate commands: the first adds to the current color amount; the second
resets **all** effects. Use one at a time to see the difference!

## Make the change happen gradually

```python
fade = hero.animate_effect(Effect.GHOST, to=100, seconds=1)
hero.animate_effect(Effect.GHOST, to=0, seconds=1, after=fade)
```

`to` is the destination. `seconds` says how long to take. Add `easing=Ease.OUT`
(with `Ease` imported) to start quickly and finish gently.

A script makes a reusable flash:

```python
flash = (
    hero.sequence()
    .animate_effect(Effect.BRIGHTNESS, to=70, seconds=0.05)
    .animate_effect(Effect.BRIGHTNESS, to=0, seconds=0.2)
)
hero.on_hit(flash)
```

Use that last line in a game with physics to flash when the hero bumps something.
Each job waits for the previous job in its script. Movement and different effects
can run together. Two animations changing the **same effect** compete: the newer
one cancels the older one's whole action. `clear_effects()` stops effect animations
and resets the appearance.

Pause freezes the animation. Stopping it keeps the current look; finishing keeps
its final look. A clone copies the current look, then has its own effects.
A Puppet fades as one character, including overlapping parts.

Effects change pictures, not bodies: an invisible hero can still bump a wall, and
its speech bubble stays readable. Effects also keep the picture's size and anchor.

**Make it yours:** change the bird's color animation to a whirl. Or combine a
pixelated dinosaur with a brightness flash!
