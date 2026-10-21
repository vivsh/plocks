# Give your dinosaur a bigger jump

[Home](../index.md) · [More activities](index.md)

**Goal:** change how your dinosaur jumps and lands.

## 1. Try the jumper

[Download Dino Dash](../dino-run/assets.md), unzip it, and open `03_jump.py`.
Run `python 03_jump.py`. Let the dinosaur land, then press Space.

`Stage()` leaves physics off: characters stay where you put them.
`Stage(physics=True)` turns on **physics**: gravity pulls things down, and solid
ground holds them up. `dino.body` lets you change how the dinosaur's body behaves.

## 2. Push harder

Find `impulse(y=460)` in the jump function. Change `460` to `520`.
An **impulse** is a quick push. Run the file again. Does the dinosaur jump higher?
`grounded` stops it jumping a second time in midair.

## 3. Try floaty gravity

After the line that makes `stage`, add:

```python
stage.physics.gravity = (0, -700)
```

Run it again. The dinosaur should fall more slowly. Try one change at a time!

## What else can a body do?

- `body.velocity` controls speed. Keep its y speed when changing sideways movement.
- `body.force(...)` gives a steady push; `body.torque(...)` twists a body.
- `body.friction` changes grip; `body.bounce` changes bounciness.
- `body.shape` is its invisible hit box. Changing an image does not change that box.

For a physical jumper, use pushes instead of glides. Glides are for a path you
choose yourself, like the hop in [movement scripts](movement.md).

**Next challenge:** play [Sky Steps](../../src/plocks/_games/platformer/README.md).
Find `hero.body.rotation_locked = True`: it keeps the hero upright.
The moving lift uses `BodyType.KINEMATIC`; the ground stays still.


## Jump through a platform

In Sky Steps, the lift has `one_way=True`. You can jump through it from below and
land on top. Every player can use it independently.

For a new platform in that game:

```python
ledge = Sprite(
    assets / "platform.png",
    body_type=BodyType.STATIC,
    one_way=True,
)
ledge.position = (0, 30)
stage.add(ledge)
```

For tiles, use `one_way={"P"}` and put `P` cells in your map. Keep those keys out
of `solid`: solid tiles block every side. Both need `Stage(physics=True)` for
automatic landing. One-way platforms stay horizontal; moving lifts use
`BodyType.KINEMATIC`.

If a tiny hit box moves too fast, Plocks may ask for more physics steps than it
can safely run. Slow the object down or give it a larger hit box.
