# Upgrade to 0.2.1

This revision replaces public Block classes with synchronous commands and actor-bound groups.
There are no compatibility aliases. Python 3.12+ and the pygame-ce foundation remain unchanged.

| Previous API | 0.3 |
|---|---|
| `hero.act(Sequence(...))` | `hero.act(hero.sequence().move(...).wait(...))` |
| `Loop(...)`, `Repeat(n, ...)` | `hero.repeat()`, `hero.repeat(n)` |
| `GlideBy(...)` | `hero.glide_by(...)` or `group.glide_by(...)` |
| `Costumes(...)`, `Poses(...)` | `costumes(...)`, `poses(...)` methods |
| `During(...)` | `hero.during(foreground, meanwhile=background)` |
| `If`, `Condition` | Ordinary typed function passed to `call` |
| `Script(...)` | Typed callback returning Action, or an advanced async callback |
| `Say`, `Think`, `ClearBubble` | `say`, `think`, `clear_bubble` methods |
| Payload-to-Block factory | Typed message callback returning Action |
| `act(..., restart=True)` | Cancel the previous Action, then start a fresh execution |
| `stop(block)` | `stop(action)` or `action.cancel()` |

Command methods now schedule work and return immediately. This includes methods
that used to be immediate: `move`, turns, pointing, bounce, dialogue, and part replacement.
Use property assignment for immediate state edits, including setup before stage membership.
Commands made while paused wait for resume.

Old `await hero.glide_by(...)` still sequences movement, but the call itself now
schedules it. Awaiting observes the same Action. Do not discard a command expecting
it to remain unstarted until awaited.

Return the last Action from an event callback to preserve busy handling and scope
newly created work. Returning None deliberately leaves created actions independent.
Each `act(group)` starts a fresh snapshot; calling it every update starts many actions.
Use an event, a repeating group, or retain an Action when explicit lifecycle control is useful.

Groups belong to one actor. Use functions accepting actors to reuse recipes.
Removing actors cancels work. Tile maps now belong to at most one stage.
`on_update` observes state at the start of the simulation interval, before physics.
The simulation tick advances after integration.

Physics is included in the default installation. Games remain nonphysical unless constructed with
`Stage(physics=True)`. See the [physics guide](physics.md).
