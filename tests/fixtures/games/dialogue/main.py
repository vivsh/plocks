"""Dialogue."""

from PIL import Image

from plocks import Script, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (32, 40), "orange"), x=-80, y=-40)
    stage.add(hero)
    hero.on_start(
        Script(Sprite)
        .say("Hello!", seconds=2)
        .think("Where should I go?", seconds=1)
        .glide_by(x=100, seconds=1)
        .say("Here looks good.")
    )
    stage.run()


if __name__ == "__main__":
    main()
