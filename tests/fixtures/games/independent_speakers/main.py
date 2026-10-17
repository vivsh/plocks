"""Independent speakers."""

from PIL import Image

from plocks import Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (32, 40), "orange"), x=-100, y=30)
    friend = Sprite(Image.new("RGBA", (28, 28), "skyblue"), x=100, y=-70)
    stage.add(hero)
    stage.add(friend)
    hero.on_start(
        hero.sequence().during(
            hero.sequence().glide_by(x=100, seconds=2),
            meanwhile=hero.sequence().say("Watch me walk!", seconds=2),
        )
    )
    friend.on_start(
        friend.sequence()
        .think("My turn next...", seconds=1)
        .say("I can move too!")
        .act(
            friend.repeat().act(
                friend.sequence().glide_by(x=-80, seconds=1).glide_by(x=80, seconds=1)
            )
        )
    )
    stage.run()


if __name__ == "__main__":
    main()
