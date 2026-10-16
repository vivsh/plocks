# Falling, jumping and moving platforms

Physics is included in the default installation. From your checkout:

```sh
python -m pip install -e .
plocks run examples/physics_playground
```

Use arrows to walk, Space to jump, and T to spin the crate. The blue lift runs a
repeating glide recipe.

Create `Stage(physics=True)`. Added Sprites and Puppets become dynamic bodies by
default. TileMap solid cells become static rectangular terrain; TiledBackground
remains decoration. Every tile is fully solid: one-way platforms and slopes are not included.

```python
from plocks import Action, Key

hero.body.rotation_locked = True


@hero.on_key_down(Key.SPACE)
def jump() -> Action | None:
    if hero.body.grounded:
        return hero.body.impulse(y=350)
    return None


@hero.on_update
def walk(dt: float) -> None:
    direction = int(stage.keyboard.is_down(Key.RIGHT))
    direction -= int(stage.keyboard.is_down(Key.LEFT))
    _, vertical = hero.body.velocity
    hero.body.velocity = (direction * 140, vertical)
```

Positions are pixels, velocity pixels/second, gravity pixels/second². Mass is a game
unit; an impulse of 350 gives a mass-1 body a 350 pixels/second velocity change.
Positive torque turns clockwise. `force(x=..., y=..., seconds=...)` and
`torque(amount, seconds=...)` apply over simulated time; omit duration for one fixed
step. Forces add together. `at=(x, y)` is a world application point; omitting it
uses the current center of mass. These commands return Actions and accept `after`.

Choose `BodyType.DYNAMIC`, `STATIC`, `KINEMATIC`, or `NONE` at construction.
Change `actor.body_type` only while detached. Kinematic actors can glide and push
other bodies; dynamic actors use velocity, impulses and forces. Direct position
assignment teleports and preserves velocity. Gliding a dynamic/static body raises
PhysicsError. `NONE` keeps ordinary authored motion even in a physical stage.

A collider snapshots local image bounds when attached. Changing costume or pose
does not resize it. Set an explicit `Box(width, height, center=...)` or
`Circle(radius, center=...)` through `body.shape`. Scale rebuilds that shape.
A Puppet has one rigid body for the whole rig. It is not a ragdoll.

Defaults: gravity `(0, -900)`, mass `1`, friction `0.7`, bounce `0`, rotation unlocked.
`rotation_style` affects appearance only; use `body.rotation_locked` to constrain
physical rotation. Symmetric centered colliders are convenient for mirrored characters.
`body.touching(...)` and `body.grounded` inspect current native contacts; actor.touching
continues to use visual bounds. Teleports do not leave stale grounded reports.

Physics is fixed for a stage's lifetime. `stage.physics` and `actor.body` remain typed
properties but raise PhysicsError when unavailable. Removing an actor invalidates
its Body. Re-add creates a new attachment with default velocity, mass, material and
shape. Reapply custom settings explicitly; never reuse an old Body handle.

Solid tile edits and map movement update collision geometry immediately. A failed edit
preserves cells and native terrain. Stages support up to 4096 solid cells. No automatic
character controller, one-way landing logic, or physical joints are included.
