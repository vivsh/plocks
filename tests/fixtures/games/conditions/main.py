from PIL import Image as PillowImage

from plocks import GamepadButton, GamepadDown, Key, Script, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    stage.gamepads[0].map_key(Key.RIGHT, GamepadButton.RIGHT)
    hero = Sprite(PillowImage.new("RGBA", (24, 24), "orange"), x=-80)
    friend = Sprite(PillowImage.new("RGBA", (24, 24), "skyblue"), x=80)
    stage.add(hero)
    stage.add(friend)

    behavior = (
        Script()
        .repeat()
        .when(
            GamepadDown(GamepadButton.RIGHT, gamepad=stage.gamepads[0]),
            then=Script().move(2),
            either=Script().wait(0),
        )
    )
    hero.act(behavior)
    stage.run()


if __name__ == "__main__":
    main()
