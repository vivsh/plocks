from PIL import Image

from plocks import Ease, Event, Key, Script, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (24, 24), "orange"), x=-80)
    friend = Sprite(Image.new("RGBA", (24, 24), "skyblue"), x=80)
    stage.add(hero)
    stage.add(friend)

    @hero.on_key_down(Key.SPACE)
    def jump(event: Event[Sprite, Key]) -> Script[Sprite]:
        return (
            Script(Sprite)
            .glide_by(y=100, seconds=0.3, easing=Ease.OUT)
            .glide_by(y=-100, seconds=0.3, easing=Ease.IN)
        )

    stage.run()


if __name__ == "__main__":
    main()
