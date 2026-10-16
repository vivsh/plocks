# API guide

## Coordinates and assets

| Setting | Meaning |
|---|---|
| Position | Costume anchor in world pixels; center origin, x right, y up |
| Direction | Clockwise degrees from up; 90 displays an unrotated image |
| Scale | Positive uniform multiplier; 1 is original size |
| Time | Simulated seconds; default 60 fixed updates per second |
| Layer | Increasing integers, with insertion order breaking ties |
| Camera | World position at the viewport center |
| TileMap x, y | Top-left world corner; rows extend downward |

`Costume`, `Sprite`, and `SpriteSheet` accept image paths or Pillow images. Images
are copied into immutable RGBA assets; later Pillow edits cannot change them.
`Costume.to_pillow()` returns an independent copy. Shared costumes need no pixel copy.
`SpriteSheet.frames()` returns row-major costumes; `frames(row=1)` selects a row.
PNG, JPEG and WebP are supported. OGG/Vorbis is the portable sound format.

## Commands and direct state

Both Sprite and Puppet provide `move`, `move_to`, `glide_by`, `glide_to`, `wait`,
`turn_left`, `turn_right`, `point_towards`, `go_to_random`, `bounce_on_edge`,
`say`, `think`, `clear_bubble`, `play_sound`, and `call`.
Every command returns an `Action` and accepts `after=...`. Commands require an actor
attached to an open stage. Calls schedule work; effects begin in an eligible action phase.
Startup work may be scheduled before `stage.run()`.

Properties are direct state: `hero.x += 1`, `hero.position = (0, 0)`,
`hero.costume = idle`, and `person.pose = rest` apply immediately.
`rotation_style` controls appearance: `ALL_AROUND`, `LEFT_RIGHT`, or `NONE`.
Exact vertical headings use the unmirrored image.

`Sprite.set_costume` and `Sprite.costumes` schedule appearance. Puppet provides
`set_pose`, `poses`, and `set_part_costume`. Changing a part does not interrupt poses.

## Actions and recipes

An Action exposes `done`, `cancelled`, `exception`, `cancel()`, and advanced `await`.
The stage owns execution even if you discard the handle. Failure is reported through
the stage with the original traceback. An awaited canceled Action raises `ActionCancelled`.

`sequence()` records one pass; `repeat(n)` records n passes; `repeat()` is indefinite.
Methods return the builder for chaining. `act(group)` snapshots and starts it.
Groups are bound to one exact actor. Nested `group.act(other)` snapshots at insertion.
`during(foreground, meanwhile=background)` stops background work when foreground finishes.
`stage.join(first, second)` waits for independent actions without taking ownership of them.

Only timed operations claim properties. An x glide and a y glide can coexist.
A new x writer cancels the previous writer's entire structured behavior. A direct x
assignment does the same. Pending `after` commands claim nothing. Conflicting timed
branches inside one `during` raise `StageError`.

Canceling freezes movement and visual sampling, clears that execution's timed bubble,
and stops a sound it is waiting for. It does not run remaining recipe steps or restore
an idle costume. `hero.stop()` cancels owned behavior; `hero.stop(action)` requires
that actor's action. `action.cancel()` is the general cancellation operation.

`after` must refer to the same stage. Canceling a predecessor cancels pending dependents.
Canceling a join does not cancel its independent inputs. Canceling a joined input cancels the join.

## Events and continuous updates

Actor `on_start`, `on_key_down`, `on_click`, and `on_message` accept groups or typed
callbacks. Stage forms observe game-wide events. Actor clicks target the topmost
visible actor; stage click callbacks observe all clicks. Payload callbacks take the
message's declared type. Click callbacks take `(Point, MouseButton)`.

A callback returning Action owns actions it created during that invocation and stays
busy until its result completes. Remaining owned work is canceled then. A callback
returning None finishes immediately; scheduled work remains independent. Existing
returned actions are borrowed. Busy events default to `WhenBusy.IGNORE`; `RESTART`
cancels and replaces the previous invocation. Relative restarts use the current position.

Key-down events occur only on an up-to-down transition. For held keys use:

```python
@hero.on_update
def update(dt: float) -> None:
    if stage.keyboard.is_down(Key.RIGHT):
        hero.x += 100 * dt
```

`on_update` and `stage.on_draw` require synchronous functions returning None.
Canvas drawing is transient, camera-independent, and drawn after scene objects and
bubbles. There is no actor on_draw; use costume assets or the stage overlay.

## Messages, pause and lifetime

`broadcast` completes after FIFO delivery. `broadcast_and_wait` also waits for the
accepted receiver invocations. Skipped busy receivers are excluded. Payloads are
passed by reference; frozen dataclasses are convenient for several typed fields.
Messages sent during delivery wait for a later cycle. Names are diagnostic only.

Pause stops time, scripts, physics and audio. Synchronous input and existing-message
callbacks and drawing continue. Newly scheduled commands wait for resume. Suspension
clears held input, and resume resets wall timing. Fixed updates cap catch-up at five
steps and drop whole-step excess; overloaded simulation slows instead of jumping ahead.

Removal cancels behavior and clears bubbles; re-add does not resume it. Event bindings
remain with their original stage and are skipped while detached. A stage runs once.
Closure clears actions, memberships, registrations, pending events, voices and native resources.

Work is bounded: 128 live execution units, 256 pending message deliveries, 256 immediate
operations per fiber per step, 4096 commands per recipe and 32 nesting levels.
Cooperative execution cannot interrupt an ordinary Python function that never returns.

## Worlds and sound

Tile maps are rectangular editable grids with a fixed palette. `get_tile`, `set_tile`,
`cell_at`, and `tiles_touching` use zero-based rows/columns. `TiledBackground` is visual
repetition; its offset is independent of the world camera. Visual `touching` uses AABB
overlap; transparent padding counts, edge-only contact does not, and visibility is irrelevant.

`stage.play(sound)` is advanced immediate playback returning a Voice. There are 16
channels; exhaustion raises AudioError. Each occurrence is independently controlled.
`play_sound(..., wait=True)` schedules playback and waits for its channel to finish.
See [physics](physics.md) for physical terrain and native contacts.
