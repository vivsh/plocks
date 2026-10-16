"""Dialogue."""

from PIL import Image

from plocks import Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (32, 40), "orange"), x=-80, y=-40)
    stage.add(hero)
    hero.on_start(
        hero.sequence()
        .say("Hello!", seconds=2)
        .think("Where should I go?", seconds=1)
        .glide_by(x=100, seconds=1)
        .say("Here looks good.")
    )
    stage.run()


if __name__ == "__main__":
    main()
