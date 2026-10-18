"""Independent speakers."""

from PIL import Image

from plocks import Script, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (32, 40), "orange"), x=-100, y=30)
    friend = Sprite(Image.new("RGBA", (28, 28), "skyblue"), x=100, y=-70)
    stage.add(hero)
    stage.add(friend)
    hero.on_start(
        Script(Sprite).during(
            Script(Sprite).glide_by(x=100, seconds=2),
            meanwhile=Script(Sprite).say("Watch me walk!", seconds=2),
        )
    )
    friend.on_start(
        Script(Sprite)
        .think("My turn next...", seconds=1)
        .say("I can move too!")
        .call(
            Script(Sprite)
            .repeat()
            .call(Script(Sprite).glide_by(x=-80, seconds=1).glide_by(x=80, seconds=1))
        )
    )
    stage.run()


if __name__ == "__main__":
    main()
