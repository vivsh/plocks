# Speech and thought bubbles

Use `Say` and `Think` inside a behavior, or `actor.say` and `actor.think` for immediate
changes. Both Sprite and Puppet support them. Omit the duration for persistent text;
a timed block waits in simulation time and clears when it finishes or is canceled.
`ClearBubble()` is the block equivalent of `actor.clear_bubble()`.

Replacing timed speech cancels the entire behavior that owns it. If a During combines
speech and movement, replacing that speech also stops that movement. Give unrelated
movement its own behavior when it should continue independently. Persistent bubbles
survive `stop()`; removal clears them. Old timers cannot erase newer speech.

Set `stage.bubble_text_size` for a larger or smaller logical font. Text stays upright,
wraps at the viewport edges, and uses an ellipsis when space is insufficient. Hidden
and off-screen actors still advance their speech timers. Custom Canvas overlays draw
above bubbles; continue using Canvas.text for scores and other screen text.


These examples keep game setup and callbacks local to main. The final statement in
main is stage.run; there is no code relying on desktop/browser post-run equivalence.

## Sequential dialogue and movement

```python
from PIL import Image
from plocks import GlideBy, Say, Sequence, Sprite, Stage, Think


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (32, 40), "orange"), x=-80, y=-40)
    stage.add(hero)
    hero.on_start(Sequence(
        Say("Hello!", seconds=2),
        Think("Where should I go?", seconds=1),
        GlideBy(x=100, seconds=1),
        Say("Here looks good."),
    ))
    stage.run()


if __name__ == "__main__":
    main()
```

The last message persists. The earlier timed messages clear before their sequence
continues. To speak while moving, use During as in the next example.

## Two independent actors, including speaking while moving

```python
from PIL import Image
from plocks import During, GlideBy, Loop, Say, Sequence, Sprite, Stage, Think


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (32, 40), "orange"), x=-100, y=30)
    friend = Sprite(Image.new("RGBA", (28, 28), "skyblue"), x=100, y=-70)
    stage.add(hero)
    stage.add(friend)

    hero.on_start(During(
        GlideBy(x=100, seconds=2),
        meanwhile=Say("Watch me walk!", seconds=2),
    ))
    friend.on_start(Sequence(
        Think("My turn next...", seconds=1),
        Say("I can move too!"),
        Loop(Sequence(
            GlideBy(x=-80, seconds=1),
            GlideBy(x=80, seconds=1),
        )),
    ))
    stage.run()


if __name__ == "__main__":
    main()
```

Each actor owns one independent bubble. Replacing hero's timed dialogue cancels
that hero During, not friend's behavior. The friend's persistent speech follows
its patrol without an active bubble timer.

## Immediate replacement and clearing

```python
from PIL import Image
from plocks import ClearBubble, Key, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (32, 40), "orange"))
    stage.add(hero)
    hero.say("Press Space to think; C to clear.")

    @stage.on_key_down(Key.SPACE)
    def wonder() -> None:
        hero.think("What shall we make?")

    @stage.on_key_down(Key.C)
    def clear() -> None:
        hero.clear_bubble()

    hero.on_key_down(Key.ESCAPE, ClearBubble())
    stage.run()


if __name__ == "__main__":
    main()
```

C's synchronous handler also clears while paused. The Escape block waits for the
next eligible script phase, so it does not execute while paused.

## Typed event handler displaying changing text

```python
from PIL import Image
from plocks import Broadcast, Key, Message, Say, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue", bubble_text_size=28)
    hero = Sprite(Image.new("RGBA", (32, 40), "orange"))
    stage.add(hero)
    score_added = Message[int]("score added")
    score = 0

    @stage.on_message(score_added)
    def show_score(amount: int) -> None:
        nonlocal score
        score += amount
        hero.act(Say(f"Score: {score}", seconds=2))

    hero.on_key_down(Key.SPACE, Broadcast(score_added, 1))
    stage.run()


if __name__ == "__main__":
    main()
```

Each event constructs a fresh block and therefore fresh text. The new timed speech
replaces the older score bubble when its execution starts. This uses existing
Message[int] typing and ordinary Python local state, not proposed Variable handles.
For same-cycle replacement in a synchronous callback use hero.say(f"Score: {score}")
instead; that text remains until explicitly cleared or replaced.
