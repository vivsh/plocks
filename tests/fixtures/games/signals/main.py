from PIL import Image

from plocks import Action, Key, Signal, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (24, 24), "orange"), x=-80)
    friend = Sprite(Image.new("RGBA", (24, 24), "skyblue"), x=80)
    stage.add(hero)
    stage.add(friend)
    dance = Signal("dance")

    @hero.on_key_down(Key.SPACE)
    def send() -> Action:
        return stage.broadcast(dance)

    friend.on_message(
        dance, friend.sequence().glide_by(y=60, seconds=0.3).glide_by(y=-60, seconds=0.3)
    )
    stage.run()


if __name__ == "__main__":
    main()
