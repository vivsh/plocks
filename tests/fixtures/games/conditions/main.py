from PIL import Image

from plocks import Action, Key, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (24, 24), "orange"), x=-80)
    friend = Sprite(Image.new("RGBA", (24, 24), "skyblue"), x=80)
    stage.add(hero)
    stage.add(friend)

    def choose() -> Action:
        if stage.keyboard.is_down(Key.RIGHT):
            return hero.move(2)
        return hero.wait(0)

    hero.act(hero.repeat().call(choose))
    stage.run()


if __name__ == "__main__":
    main()
