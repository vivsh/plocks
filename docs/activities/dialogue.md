# Say hello! 💬

[Home](../index.md) · [More activities](index.md)

**Goal:** make a dinosaur speak, think, and scoot across the stage.

1. [Download Dino Dash](../dino-run/assets.md) and unzip it.
2. Save this as `hello.py` inside its `dino_run` folder.
3. Run `python hello.py` and watch the bubbles.

```python
from pathlib import Path

from plocks import Image, Sprite, Stage

assets = Path(__file__).resolve().parent / "assets"
stage = Stage(background="midnightblue")
hero = Sprite(Image(assets / "dinosaur.png").resized(width=72, height=72))
stage.add(hero)

chat = hero.sequence()
chat.say("Hello!", seconds=2)
chat.think("Where shall I go?", seconds=1)
chat.glide_by(x=100, seconds=1)
hero.on_start(chat)

if __name__ == "__main__":
    stage.run()
```

`seconds=2` shows the words for two game seconds. The script waits, but other
characters can keep moving. Each character has one bubble at a time.

Without `seconds`, `hero.say("Hello!")` stays until replaced or cleared.
`hero.think("Hmm...")` replaces speech with a thought.
`hero.clear_bubble()` removes it. Connect calls with `after`, or put them in a script.

Bubbles follow the character and stay upright. Want bigger writing? Put
`stage.bubble_text_size = 30` after making the stage.

**Make it yours:** change the words, then add one more `chat.say(...)` before
`hero.on_start(chat)`. Add a second Sprite to have two characters speak!

For changing numbers, build your words inside an event function, as in
[the memory activity](memory.md). A script's f-string remembers its words when
you make the script, rather than reading the number again later.
