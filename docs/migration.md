# Migrating to Plocks

The project was renamed from Scratchpy to Plocks. Update imports to `plocks`,
use the `plocks` command, rename `scratchpy.toml` to `plocks.toml`, and replace
`ScratchpyError` with `PlocksError`. There are no old-name compatibility aliases.
Reinstall the local checkout after renaming.

## Moving from 0.1 to 0.2

This revision intentionally breaks the earlier API. There are no compatibility aliases.

| Earlier API | Current API |
| --- | --- |
| `sprite.play(Animation(frames, fps=10))` | `sprite.act(Loop(Costumes(frames, fps=10)))` |
| Nonlooping animation | `sprite.act(Costumes(frames, fps=10))` |
| `stop_animation()` | `stop(recipe)` or `stop()` |
| `is_animating` | Put the next action after the animation in a `Sequence` |
| `StickFigure` | `Puppet.stick_figure()` or image-part `Puppet(...)` |
| `PoseAnimation` | `Poses`, with `Loop` or `Repeat` as needed |
| Automatic pose-loop closing | Repeat the first pose at the end explicitly |
| Re-add resumes playback | Removal cancels; start the desired block again |
| Replaying a completed definition stays completed | `act` starts a new execution after completion |

Joint geometry changed deliberately: `Joint(parent, offset=(x, y), angle=...)`
defines a pivot. Its own angle rotates its image and descendants, not its offset
from its parent. Re-author old bone-endpoint rigs rather than copying old angle
mappings unchanged. Images provide all appearance, including the stick preset.

Actors belong to one Stage at a time. Add them before binding behavior. A direct
position or appearance assignment interrupts the active writer's entire enclosing
behavior. Use independent axes when a patrol and jump should coexist.
