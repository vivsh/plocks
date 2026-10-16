# Let actors talk

```python
from PIL import Image
from plocks import Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (32, 40), "orange"))
    stage.add(hero)

    dialogue = hero.sequence()
    dialogue.say("Hello!", seconds=2)
    dialogue.think("Where next?", seconds=1)
    dialogue.glide_by(x=100, seconds=1)
    hero.on_start(dialogue)
    stage.run()


if __name__ == "__main__":
    main()
```

`hero.say("Hello!")` schedules persistent speech and completes once displayed.
`hero.think("Hmm...")` replaces it. `hero.clear_bubble()` schedules clearing.
Use `after` to connect independent calls, or put them in a sequence. Both Sprite
and Puppet have one bubble slot. Two actors speak independently.

Timed speech waits using simulation time. Pause stops its clock; commands made
while paused wait for resume. Replacing timed speech cancels the previous writer's
whole structured behavior. An old timeout never clears a newer bubble. Removal and
cancellation clear owned timed speech; persistent speech remains until explicitly
replaced, cleared, or the actor is removed.

F-strings are evaluated when the command is constructed. Use a named function with
`call` to capture a changing value later:

```python
from plocks import Action


def announce() -> Action:
    return hero.say(f"Score: {score}", seconds=1)


hero.call(announce, after=finished)
```

Empty or whitespace-only text clears. Newlines and word wrapping are supported;
very long text is clipped with an ellipsis. Text stays upright as actors turn or
scale. Bubbles follow the actor and camera, stay inside the viewport, and are hidden
with their actor or when it is fully off screen. Drawing callbacks appear above them.
`stage.bubble_text_size` changes the logical font size for accessibility (default 24).
