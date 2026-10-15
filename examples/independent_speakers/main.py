"""Independent speakers."""

from PIL import Image

from plocks import During, GlideBy, Loop, Say, Sequence, Sprite, Stage, Think


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (32, 40), "orange"), x=-100, y=30)
    friend = Sprite(Image.new("RGBA", (28, 28), "skyblue"), x=100, y=-70)
    stage.add(hero)
    stage.add(friend)

    stage.on_start(
        hero,
        During(
            GlideBy(x=100, seconds=2),
            meanwhile=Say("Watch me walk!", seconds=2),
        ),
    )
    stage.on_start(
        friend,
        Sequence(
            Think("My turn next...", seconds=1),
            Say("I can move too!"),
            Loop(
                Sequence(
                    GlideBy(x=-80, seconds=1),
                    GlideBy(x=80, seconds=1),
                )
            ),
        ),
    )
    stage.run()


if __name__ == "__main__":
    main()
