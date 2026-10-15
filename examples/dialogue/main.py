"""Dialogue."""

from PIL import Image

from plocks import GlideBy, Say, Sequence, Sprite, Stage, Think


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (32, 40), "orange"), x=-80, y=-40)
    stage.add(hero)
    stage.on_start(
        hero,
        Sequence(
            Say("Hello!", seconds=2),
            Think("Where should I go?", seconds=1),
            GlideBy(x=100, seconds=1),
            Say("Here looks good."),
        ),
    )
    stage.run()


if __name__ == "__main__":
    main()
