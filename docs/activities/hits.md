# Bumps, overlaps and bright beams

[Home](../index.md) · [More activities](index.md)

Try **Railgun Range**:

```sh
plocks run railgun
```

Walk with the arrows, jump with Space, fire with X and reset with R.
Blast the top bricks, then zap the robots behind them!

## Did my body hit something?

On a `Stage(physics=True)`, `on_hit` notices physical shape contact:

```python
from plocks import Collision, Event, Sprite

@hero.on_hit
def bumped(event: Event[Sprite, Collision]) -> None:
    other = event.data.target
    print("Bumped into", other)
```

`event.target` is your hero. `event.data.target` is the other Sprite, Puppet or
TileMap. Both actors can have their own hit handlers. You choose damage and sounds;
physics controls how their bodies move.

| `event.data` field | What it tells you |
| --- | --- |
| `target` | The other character or tile map |
| `point` | Where contact happened, in world coordinates |
| `normal` | Which way points out of the other surface towards your hero |
| `cell` | A tile's `(row, column)`, or `None` for characters |

A hit happens when contact begins. Standing on a floor doesn't keep calling it.
Step away and return to get another hit. Adjacent tiles in one map count as one
contact episode; `cell` names one contacted tile.

Custom collision shapes, rotation and collision filters affect physical hits.
A sensor can report contact without pushing or blocking. Puppets work too.

## Are our pictures overlapping?

`on_touch` checks the rectangles around pictures and works without physics:

```python
@hero.on_touch(enemy)
def overlap(event: Event[Sprite, Sprite]) -> None:
    event.target.say("Hello!", seconds=1)
```

It accepts one Sprite, Puppet or TileMap. Both objects must be added to the same
stage first. For tiles it checks solid and one-way cells:

```python
from plocks import TileMap

@hero.on_touch(world)
def overlap_tiles(event: Event[Sprite, TileMap]) -> None:
    cells = event.data.tiles_touching(event.target.bounds)
    print(cells)
```

Use `on_touch_end(other)` to notice when the overlap ends. Transparent picture
padding counts in these rectangles. Physical collision filters don't change them.

## How does the railgun glow?

Open the example's [fire function](../../src/plocks/_games/railgun/main.py).
A `raycast()` finds the first target immediately. The firing function applies damage
and draws three thin image sprites: blue glow, pale blue light and a white core.

```python
beam = Sprite(beam_image, body_type=BodyType.NONE)
stage.add(beam)
beam.remove_after(seconds=0.12)
```

The beam's lifetime uses game time, so pause freezes the flash. It has no body and
doesn't block future rays. The railgun works in either facing direction. Copy the
game to edit it:

```sh
plocks examples railgun --copy-to my-railgun
python my-railgun/main.py
```

A ray is a query: your firing function applies damage from its result. It doesn't
call `on_hit` automatically. A flying bullet instead uses `body.projectile = True`
for swept physical hits, including thin walls between ticks. Sensor crossings
notify without stopping the bullet; blocking surfaces stop it.

**Type hint tip:** hit callbacks use `Collision`. Ray and shape queries return
`CastHit`, which also has travel `distance`. Older hit handlers annotated with
`CastHit` should change that annotation to `Collision`.

**Make it yours:** change the glow colors, shorten the flash, or give robots health
so they take two shots.
