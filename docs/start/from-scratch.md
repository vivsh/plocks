# From Scratch to Plocks 🧩

[Home](../index.md) · [Start here](index.md)

You already know how to make characters do things. Now tell them using Python!
Plocks keeps familiar ideas: sprites, costumes, the stage, and broadcasts.

| In Scratch | In Plocks |
| --- | --- |
| Stage | `stage = Stage()` |
| Add a sprite | `hero = Sprite(picture)` then `stage.add(hero)` |
| When green flag clicked | `hero.on_start(script)` |
| When Space pressed | `hero.on_key_down(Key.SPACE, script)` |
| Move 10 steps | `hero.move(10)` |
| Go to x/y | `hero.position = (100, 20)` |
| Glide | `hero.glide_to(x=100, seconds=1)` |
| Say / think | `hero.say("Hello!")` / `hero.think("Hmm...")` |
| Wait | `script.wait(1)` |
| Repeat / forever | `hero.repeat(10)` / `hero.repeat()` |
| Broadcast | A shared `Message` token and `broadcast(...)` |
| Variables | Normal Python names, or typed dataclass state |

## Make your first hop

1. [Set up Plocks](index.md) with a grown-up.
2. [Download Dino Dash](../downloads/dino-dash.zip). Unzip it.
3. Save this as `scratch_hop.py` **inside its dino_run folder**, then run
   `python scratch_hop.py`.

```python
from pathlib import Path

from plocks import Costume, Ease, Key, Sprite, Stage

assets = Path(__file__).resolve().parent / "assets"
stage = Stage(background="#fff0cc")
hero = Sprite(Costume(assets / "dinosaur.png").resized(width=72, height=72))
stage.add(hero)

# This records a script. It does not start the hop yet.
hop = hero.sequence()
hop.say("Let's hop!", seconds=0.5)
hop.glide_by(y=90, seconds=0.3, easing=Ease.OUT)
hop.glide_by(y=-90, seconds=0.3, easing=Ease.IN)
hero.on_key_down(Key.SPACE, hop)

if __name__ == "__main__":
    stage.run()
```

Press Space! More presses are ignored until the script finishes.
Change both `90` values to `120` for a bigger hop.

## Three Python tricks

- **Quotes** hold words: `"Hello!"`. `=` gives a value to a name; `==` compares values.
- **Indentation** groups lines. Use four spaces under `if` and `def`.
- **Scripts connect time.** Script lines run in order. Two ordinary glide calls
  schedule work together unless you connect them with `after=first_action`.

A function is a named job. A decorator such as `@hero.on_key_down(...)` connects
that job to an event. Functions receive one `event`: its `target` is the receiver,
`source` is who caused it, and `data` is the key, message, or other information.
You will meet these step by step in the [Dino Dash course](../dino-run/index.md).

Scratch's stage is 480 × 360; that is Plocks' default too. Its centre is `(0, 0)`;
x goes right and y goes up. **Directions differ:** Plocks uses 0 up, 90 right,
180 down, 270 left. Scratch uses 0 up and -90 left.

**Your next adventure:** [learn Python while building Dino Dash](../dino-run/index.md).
Draw costumes with [Pixelorama](../art/pixelorama.md), or paint levels with [Tiled](../art/tiled.md).
