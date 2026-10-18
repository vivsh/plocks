from PIL import Image

from plocks import Key, KeyDown, Script, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (24, 24), "orange"), x=-80)
    friend = Sprite(Image.new("RGBA", (24, 24), "skyblue"), x=80)
    stage.add(hero)
    stage.add(friend)

    behavior = (
        Script().repeat().when(KeyDown(Key.RIGHT), then=Script().move(2), either=Script().wait(0))
    )
    hero.act(behavior)
    stage.run()


if __name__ == "__main__":
    main()
