# Learn Plocks with blocks

Run a lesson with `plocks run examples/<lesson>`.

1. **first_steps** — construct a Sprite from Pillow, add it, bind Right to a glide.
2. **jump_patrol** — compose a jump with two glides; another actor patrols independently.
3. **walking_costumes** — use `During` to change costumes while moving.
4. **conditions** — test held input with `If(KeyDown(...), then=...)` in a loop.
5. **signals** — one actor broadcasts an event that starts another actor's blocks.
6. **messages** — send a frozen typed payload; a small function creates receiver blocks.
7. **puppet** — animate a generated human using complete poses and `HumanJoint` names.
8. **custom_figure** — attach images at joint pivots to make a custom articulated arm.
9. **scripts** — advanced async functions await the same motion primitives.
10. **animated_world** — combine spritesheets, Pillow art, tiles, editable cells, Puppet
    poses, sound, typed messages, a camera and a score overlay.

## Think in sequences

```python
jump = Sequence(
    SetCostume(jumping),
    GlideBy(y=100, seconds=0.3, easing=Ease.OUT),
    GlideBy(y=-100, seconds=0.3, easing=Ease.IN),
    SetCostume(idle),
)
hero.on_key_down(Key.SPACE, jump)
```

Blocks are reusable recipes. Constructing one does not start it. `actor.act(block)`
starts a behavior, or an event binding starts it when the event arrives. A shared
recipe gives each actor independent progress. You do not store timers or frame
indexes. Repeated key presses are ignored while that binding is still busy.

`Sequence` means next, `Repeat` means a fixed number of times, and `Loop` means
until stopped. `Wait` pauses one behavior while the rest of the game continues.
`During(move, meanwhile=costumes)` keeps the background scoped to the movement.

## Coordinates and immediate Python

The stage center is `(0, 0)`. Positive x is right; positive y is up. Direction is
clockwise from up, with 90 facing right. Distances are pixels and times are seconds.
A costume's anchor marks its position; a Puppet uses its skeleton's root.

Ordinary Python remains useful for continuous input, scores and derived cameras:

```python
@stage.on_update
def update(dt: float) -> None:
    if stage.keyboard.is_down(Key.RIGHT):
        hero.x += 100 * dt
```

A direct x assignment interrupts an active x glide. It does not interrupt a y-only
jump. Collision queries report overlap; they do not move the actor or supply physics.

## Run and explore

Keep `stage.run()` last. Use the project root as the working directory for relative
assets. `plocks run` sets that directory for you.

Hover over blocks, enums and methods in Pylance to see their arguments and units.
The [API guide](api.md) explains cancellation, messages, audio and advanced scripts.
The [migration guide](migration.md) covers projects written for 0.1.
