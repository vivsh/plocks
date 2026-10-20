from PIL import Image as PillowImage

from plocks import Ease, Event, GamepadButton, GamepadPress, Key, Script, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    hero = Sprite(PillowImage.new("RGBA", (24, 24), "orange"), x=-80)
    friend = Sprite(PillowImage.new("RGBA", (24, 24), "skyblue"), x=80)
    stage.add(hero)
    stage.add(friend)

    @hero.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])
    def jump(event: Event[Sprite, GamepadPress]) -> Script[Sprite]:
        return (
            Script(Sprite)
            .glide_by(y=100, seconds=0.3, easing=Ease.OUT)
            .glide_by(y=-100, seconds=0.3, easing=Ease.IN)
        )

    stage.run()


if __name__ == "__main__":
    main()
