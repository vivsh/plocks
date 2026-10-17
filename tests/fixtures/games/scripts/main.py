from PIL import Image

from plocks import Ease, Key, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (24, 24), "orange"), x=-80)
    friend = Sprite(Image.new("RGBA", (24, 24), "skyblue"), x=80)
    stage.add(hero)
    stage.add(friend)

    @hero.on_key_down(Key.SPACE)
    async def jump() -> None:
        await hero.glide_by(y=100, seconds=0.3, easing=Ease.OUT)
        await hero.glide_by(y=-100, seconds=0.3, easing=Ease.IN)

    stage.run()


if __name__ == "__main__":
    main()
