# API guide

Import names explicitly from `plocks`. Public classes and methods have ordinary
type annotations and hover documentation. Geometry requires finite numbers.
Invalid values raise `ValueError`, wrong scalar types raise `TypeError`, and invalid
lookups raise `KeyError` or `IndexError`.

## Coordinates

`Point` is `tuple[float, float]`. `Color` is a named color, hex color, or RGB/RGBA
integer tuple with channels from 0 through 255.

| Setting | Meaning |
| --- | --- |
| `Stage()` | 480 × 360 logical pixels; 60 fixed updates per second |
| Origin | Center of stage; x right, y up |
| Direction | Clockwise degrees from up; 90 displays unrotated artwork |
| Scale | Positive uniform multiplier; 1 means original size |
| Layer | Increasing integer; insertion order breaks ties |
| Costume anchor | Source-image pixels from top-left, y down; centered by default |
| Tile-map position | World top-left of its grid |
| Camera | World position at the viewport center |

`Bounds(left, bottom, right, top)` is immutable. Width, height, and center are
derived. `intersects(other)` requires positive overlap on both axes; edge contact
is false. `stage.bounds` uses stage coordinates; `stage.world_bounds` includes the
camera. `stage.to_screen(point)` and `from_screen(point)` convert world and top-left
screen pixels. Pass `world=False` to convert stage coordinates instead.

## Costumes, sprites, and animation

`Costume(source, anchor=None)` accepts a path or Pillow image. PNG, JPEG, and WebP
are supported; PNG is recommended. Missing or invalid files raise `AssetError`.
Pixels become an owned RGBA snapshot. `to_pillow()` returns an independent image.

`Sprite(source, *, x=0, y=0, direction=90, scale=1, visible=True, layer=0)` accepts a
costume, path, or Pillow image. Read or assign `x`, `y`, `position`, `direction`,
`scale`, `visible`, `layer`, and `costume`. Bounds derive from transformed image
corners, including transparent padding. Shared costumes do not copy pixels.

`move(steps)`, `move_to(x=..., y=...)`, `turn_left(degrees)`, and
`turn_right(degrees)` act immediately. `touching(other)` accepts a sprite, Puppet,
or tile map. Map collision checks solid cells. Hiding changes drawing only.
Collision queries never move objects or impose boundaries.

`SpriteSheet(source, frame_size=(w, h), margin=(0, 0), spacing=(0, 0))` requires a
complete grid. Margins apply on both sides of each axis. `frame(row=..., column=...)`
copies one frame, `frames(row=...)` returns a row tuple, and `frames()` returns all
frames in row-major order. Addressing starts at zero. Tuples support normal slicing.
Invalid grids raise `ValueError`; invalid indexes raise `IndexError`.

## Reusable blocks

After `stage.add(hero)`, call `hero.act(block)` or bind events:

```python
jump = Sequence(
    GlideBy(y=100, seconds=0.3, easing=Ease.OUT),
    GlideBy(y=-100, seconds=0.3, easing=Ease.IN),
)
hero.on_key_down(Key.SPACE, jump)
```

`act` schedules; it returns `None` and never runs inline. Before `run`, it queues
startup behavior. Reusing the same active block continues it; `restart=True`
cancels and starts again. After completion, it starts fresh. `stop(block)` stops
that exact recipe; `stop()` stops all current actor behaviors. Removing an actor
cancels behavior and re-adding does not resume it. Actors belong to one stage.

- `Sequence(first, *rest)` runs children in order.
- `Repeat(times, block)` repeats a nonnegative count; `Loop(block)` repeats forever.
- `Wait(seconds)` uses simulation time; `Wait(0)` yields a tick.
- `If(condition, then=block, otherwise=None)` tests when reached. Use `KeyDown(key)`
  and `Touching(actor_or_map)` without lambdas.
- `During(foreground, meanwhile=background)` runs both, then stops the background
  when the foreground finishes. Neither child outlives the enclosing behavior.
- `Move`, `MoveTo`, `TurnLeft`, `TurnRight`, `PointTowards`, `GoToRandom`, and
  `BounceOnEdge` apply immediate operations when reached.
- `GlideTo` and `GlideBy` use supplied x/y, `seconds`, and `easing`. Omitted axes
  remain free. Explicit zero still controls that axis. Zero seconds sets the
  endpoint and yields a tick. `Ease` has LINEAR, IN, OUT, and IN_OUT curves.

An x-only patrol can run alongside a y-only jump. A new timed writer or direct
position assignment cancels the previous writer's whole root behavior. Cancellation
freezes the current state; it does not finish remaining blocks or restore a ground
position. Two `During` branches writing the same property raise `StageError`.

`Costumes(frames, fps=...)` displays a nonempty frame tuple once, including the last
frame interval. Use `Loop(Costumes(...))` to repeat. `SetCostume(source)` is immediate.
Image sources are snapshotted at block construction. Assigning `costume` interrupts
its current timed writer. Independent actors can share one immutable block.

```python
walk = During(
    GlideTo(x=180, seconds=2),
    meanwhile=Loop(Costumes(sheet.frames(row=1), fps=10)),
)
```

`rotation_style` accepts `RotationStyle.ALL_AROUND`, `LEFT_RIGHT`, or `NONE`.
Direction still determines movement. Left/right mirrors leftward headings; exact
vertical headings are unmirrored. `point_towards` samples its target immediately.
`go_to_random(bounds=None)` samples the anchor in visible world bounds.
`bounce_on_edge(bounds=None)` reflects outward headings and fits the actor inside;
oversized actors raise `ValueError`. These are ordinary immediate methods too.

## Puppets and poses

`Joint(parent, offset=(0, 0), angle=0)` is an image pivot. Offset is in parent-local
pixels, x right/y up. Its angle rotates attached artwork and descendants around the
pivot. It does not rotate its own offset. The single root has zero offset.

`Skeleton(joints)` owns ordered definitions; parents precede children. `Pose(skeleton,
angles)` requires all joint names and finite clockwise parent-relative angles.
`with_angles(changes)` makes a complete new pose. Unknown keys fail clearly.

`Puppet(skeleton, parts={name: costume_or_image}, pose=None)` requires at least one
image attachment. A costume's anchor marks its joint pivot. Parts paint in mapping
order; keys/order remain fixed. `parts` is read-only; `set_part_costume(name, source)`
replaces an existing attachment. Nonvisual joints are allowed. Puppets have the
same movement/behavior vocabulary as sprites, with `pose` instead of `costume`.
Bounds include all transformed image corners and transparent padding.

`Puppet.stick_figure(color="white", stroke_width=4)` supplies a human with generated
image parts. `HumanJoint` provides joint-name completion. Custom rigs use string
names. `puppet.skeleton.rest_pose()` creates the corresponding complete rest pose.

`Poses(poses, fps=...)` interpolates first to last, using shortest angular paths and
clockwise 180-degree ties. Adjacent poses take `1/fps` seconds. Every pose must share
the target's exact skeleton. Repeat the first pose explicitly to close a loop:

```python
person.act(Loop(Poses((standing, raised, standing), fps=2)))
```

`SetPose(pose)` sets immediately. `SetPartCostume(name, source)` changes artwork
without interrupting pose motion. Deformable meshes, IK and rig-file import are not
supported.

## Events and messages

Add an actor to a stage, then attach its reactions directly:

```python
stage.add(hero)
hero.on_start(patrol)
hero.on_key_down(Key.SPACE, jump)
hero.on_message(dance, dance_steps)  # dance is a Signal
```

These methods accept blocks on both Sprite and Puppet. Startup registration must
happen before `stage.run()`. Key and message handlers can also be registered during
execution. Detached registration raises `StageError`. Keys are game-wide: multiple
actors can react to the same key, without keyboard focus.

Busy registrations ignore repeat triggers by default; `when_busy=WhenBusy.RESTART`
cancels and replaces their current invocation. There is no trigger backlog.
Separate registrations are independent. `stop()` cancels behavior without removing
registrations. Removal cancels behavior and makes handlers inactive; re-adding to
the same stage enables them again without replaying startup. Registrations belong
to that stage and do not move with an actor to another stage. Stage closure clears
them.

Use Stage callback decorators for game-wide logic such as scores and pause controls.
The existing `stage.on_start(actor, block)`, key and message binding forms remain
supported. Use `Script` to bind an advanced async actor function. Custom drawing
stays on Stage; actors have no `on_draw` method.

For custom continuous movement, attach a synchronous update callback:

```python
@hero.on_update
def move(dt: float) -> None:
    if stage.keyboard.is_down(Key.RIGHT):
        hero.x += 200 * dt
```

Actor and Stage updates share registration order and fixed simulated seconds.
Updates stop during pause/suspension, run even when an actor is hidden, and skip
actors detached from their registering stage. `stop()` cancels block executions;
it does not unregister update or event callbacks. Async update functions are
rejected. Changes to registrations take effect in the next update phase.

Click an actor to run a block, or receive the pointer payload in a typed callback:

```python
hero.on_click(jump)

@person.on_click
def greet(position: Point, button: MouseButton) -> None:
    person.say(f"{button.name.title()} click!")
```

Only the topmost visible Sprite or Puppet under the pointer receives actor clicks,
using layer and then later insertion order. Hit testing uses transformed world
bounds through the camera, including transparent padding; it is not pixel-mask
hit testing. Left/top edges count, right/bottom edges do not. A visible actor without
click handlers still blocks actors beneath it. Tile maps, backgrounds, bubbles,
and Canvas overlays do not intercept actor clicks.

For a variable annotated as `Actor` (`Sprite | Puppet`), use named registration
`actor.on_click(callback)` if mypy rejects decorator syntax on the union.
Decorators work directly on concrete Sprite and Puppet variables.

Click payloads stay in stage coordinates. Actor click callbacks can be synchronous
or asynchronous; block and async invocations use the normal busy policy and actor
cancellation rules. During pause, sync click callbacks run and asynchronous/block
work waits until resume. Register after adding the actor to a stage.

Stage click callbacks still observe every click and run before targeted actor
handlers. The target and handler lists are snapshotted before dispatch. Removing
the selected actor in a global observer skips it without retargeting that click.
The older `stage.on_click(actor, block)` form remains a global click binding;
prefer `actor.on_click(block)` when the actor itself should be clicked.

`Signal("name")` carries no data. `Message[int]("name")` carries a typed value.
Share the same token instance, often from a project-local messages module: identical
names do not make identical channels. Use `Broadcast(token[, data])` in blocks or
`stage.broadcast(token[, data])` in callbacks. Sends require a running stage and
queue delivery without calling receivers recursively. Emissions during delivery
wait until a later cycle. Payloads are shared by reference; frozen dataclasses are
recommended for several fields.

```python
hit = Message[int]("hit")

def recoil(distance: int) -> Block[Sprite]:
    return GlideBy(x=distance, seconds=0.2)

enemy.on_message(hit, recoil)
hero.on_key_down(Key.H, Broadcast(hit, 20))
```

Factories run only for accepted deliveries, when their behavior starts.
`@stage.on_message(hit)` also accepts a typed ordinary callback. `BroadcastAndWait`
joins only accepted invocations from that delivery. Skipped busy receivers are not
joined; cancellation counts as completion. Canceling the sender does not retract
its message or cancel receivers.

## Advanced scripts

`Script(async_actor_function)` is a block. Inside it, await `stage.wait`,
`actor.glide_to/by`, another `block.run(actor)`, or `stage.broadcast_and_wait`.
Calling an async method creates its coroutine; the action begins when awaited.
Event decorators also accept async functions, while update and draw stay synchronous.

Scripts use Plocks's simulation runner. General asyncio I/O, `sleep`, `gather`,
and detached tasks are unsupported. Unsupported awaits raise `StageError`. Python
that never yields cannot be preempted. Keep synchronous cleanup in `finally`;
awaiting during cancellation cleanup is unsupported.

Execution is bounded to 128 live coroutine branches and 256 queued messages.
Admission overflow raises `StageError`; immediate-work budgets yield execution
between ticks. All failures retain their original traceback and close the stage.

## Tile maps and backgrounds

```python
world = TileMap(
    ["....", "..##", "####"], {"#": ground},
    tile_size=(32, 32), solid={"#"}, empty=".", x=-64, y=48,
)
```

Rows must be nonempty and rectangular. Palette keys and the empty marker are single
characters. Costumes fill cells regardless of their anchors. Palette and cell size
stay fixed. `get_tile(row=..., column=...)` returns a key or `None`;
`set_tile(row=..., column=..., tile=...)` edits a cell, using `None` to clear.
`cell_at(x=..., y=...)` returns `(row, column)` or `None`; right and bottom outer
edges are outside. `tiles_touching(bounds, solid_only=True)` returns occupied,
positively overlapping cell coordinates in row-major order. Outside/negative cell
indexes raise `IndexError`; unknown palette keys raise `KeyError`.

`TiledBackground(source, area=None, offset=(0, 0), visible=True, layer=-100)` repeats
a costume over the viewport or explicit stage-coordinate `Bounds`. It ignores the
camera. Assign `offset` to scroll; positive y moves the pattern up. Derive offsets
from camera motion yourself for parallax.

## Sound

`PlaySound(sound, volume=1, wait=True)` is the block form. Waiting finishes with its
voice and cancellation stops that occurrence. With `wait=False`, the sound remains
stage-owned after the block finishes. Compose repetition with `Loop` or `Repeat`.


`Sound(path)` reads an immutable OGG/Vorbis snapshot without opening an audio
device. Other formats/codecs raise `AssetError`. In a callback, use
`voice = stage.play(sound, volume=0.8, loop=False)`. Playback requires a running
stage; one asset supports overlapping occurrences, up to 16 voices. Allocation or
device failure raises `AudioError`; existing sounds are never stolen.

`voice.finished` becomes true after completion or stop. `voice.stop()` affects only
that occurrence, even after its channel is reused. `stage.stop_sounds()` stops all
stage voices. `stage.volume` multiplies occurrence volumes, each in `[0, 1]`.
Pause pauses voices; a new sound while paused starts paused. Closing retires all
handles. Each occurrence decodes independently.

## Speech and thought

Both Sprite and Puppet have `say(text)`, `think(text)` and `clear_bubble()`.
They act immediately, including before stage membership. One actor has one bubble.

`Say(text, seconds=None)`, `Think(text, seconds=None)` and `ClearBubble()` compose
with other blocks. Omit `seconds` to set persistent text and finish the block
immediately. Supply a finite nonnegative duration to display, wait in simulation
time, clear that occurrence and continue. Pause freezes these durations. Zero
seconds yields one tick, which does not guarantee a presented frame.

```python
hero.act(Sequence(
    Say("Hello!", seconds=2),
    Think("Where next?", seconds=1),
    GlideBy(x=100, seconds=1),
    Say("Here!"),
))
```

Replacing or clearing an active timed bubble cancels its **whole root behavior**,
including movement in that root. Separate roots continue. Timed bubbles clear when
canceled; persistent text survives stopping behavior. Removal clears both kinds,
and re-adding does not restore dialogue. Competing timed bubbles in sibling During
branches raise StageError. An older timer never clears a replacement bubble.

`During(GlideBy(x=100, seconds=2), meanwhile=Say("Walking", seconds=2))` speaks
while moving and clears when either that speech ends or the enclosing behavior
ends. A persistent Say in the background finishes immediately and leaves its text.

Text must be a string. F-strings are evaluated at block construction. Use an ordinary
typed event callback to construct fresh text, as in [the dialogue lessons](dialogue.md).
Empty or all-whitespace text clears. A timed blank clears first, then waits without
owning the bubble. Newlines and tabs are supported; other ASCII control characters
are rejected. Long words wrap and text exceeding viewport space is ellipsized.

Bubbles follow transformed actor bounds and camera movement, but text remains upright
and independent of actor scale. Hidden or wholly off-screen actors have no drawn
bubble; their timers still advance. `Stage(bubble_text_size=24)` controls logical
font size for all bubbles; assignment updates existing bubbles on their next draw.
Tiny viewports or oversized text can suppress a bubble rather than shrink its font.

The bundled default font works on desktop and in both browser modes. No external
font request is needed. Glyph coverage is limited to that font; this is visual canvas
text, not a screen-reader or rich-text interface. Bubbles draw after scene objects,
in actor layer/insertion order, and before Canvas overlays. They do not affect actor
bounds, collision or input. `Canvas.text` remains the API for scores and overlays.

## Input and drawing

`stage.keyboard.is_down(Key.RIGHT)` reads held keys. `@stage.on_key_down(Key.SPACE)`
registers `() -> None` callbacks on new presses, ignoring OS repeat. Arrows, letters,
digits, and common controls are named enum members.

`@stage.on_click` registers `(position: Point, button: MouseButton) -> None`.
`stage.mouse.position` is read-only and uses stage coordinates; add the camera to
get world coordinates. `stage.mouse.is_down(MouseButton.LEFT)` reads held buttons.

`@stage.on_draw` registers `(canvas: Canvas) -> None`, above all scene objects and
unaffected by the camera. Style arguments are keyword-only:

- `line(start, end, color="white", width=1)`
- `circle(center, radius, color="white", width=0)`
- `rectangle(bounds, color="white", width=0)`
- `text(text, position, size=24, color="white", font=None)`

Width 0 fills shapes. Text position is its top-left. Optional fonts are project TTF
paths that must be included in browser builds. A Canvas is valid only inside its
callback; retaining and using it later raises `StageError`.

## Execution and failures

Assets and objects can be constructed without opening a window. `add`, `remove`,
and `clear` change stage membership; `objects` returns a snapshot. One stage runs at
a time and each runs once. Conflicting Pygame display/audio resources raise
`StageError`.

Put `run()` last in the entry script. It blocks on desktop and schedules a yielding
driver in Pygbag. Updates stay synchronous. Long callbacks block both platforms.
Each fixed step advances the tick, samples motion, dispatches queued messages and
input, advances behaviors, then invokes updates in registration order. Drawing follows the scene. Callback lists
already being dispatched use snapshots.

`pause()`/`resume()` control user pause. Updates and behaviors stop; synchronous input/message callbacks
and drawing continue. Hidden/minimized or unfocused applications suspend
automatically and clear held input. Automatic resume preserves user pause and
resets the wall-clock baseline. `stop()` ends execution and is safe to repeat.
The closed stage cannot restart.

Wall contributions clamp to 250 ms, with at most five simulation steps per rendered
frame. Excess whole-step backlog is dropped while its fraction remains; simulation
slows under sustained overload. `stage.time` measures simulated seconds.

Callback failures retain their original exception and traceback, stop execution,
and release resources. Browser errors also appear in a readable page panel.
`PlocksError` is the base for `AssetError`, `AudioError`, `StageError`, and
`BuildError`; ordinary game exceptions are not replaced.
