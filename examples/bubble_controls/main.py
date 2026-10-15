"""Bubble controls."""

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
