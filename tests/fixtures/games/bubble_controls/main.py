"""Bubble controls."""

from PIL import Image

from plocks import Event, Key, Script, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (32, 40), "orange"))
    stage.add(hero)
    hero.say("Press Space to think; C to clear.")

    @stage.on_key_down(Key.SPACE)
    def wonder(event: Event[Stage, Key]) -> None:
        hero.think("What shall we make?")

    @stage.on_key_down(Key.C)
    def clear(event: Event[Stage, Key]) -> None:
        hero.clear_bubble()

    hero.on_key_down(Key.ESCAPE, Script(Sprite).clear_bubble())
    stage.run()


if __name__ == "__main__":
    main()
