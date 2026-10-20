from PIL import Image as PillowImage

from plocks import Action, Event, GamepadButton, GamepadPress, Key, Message, Script, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    hero = Sprite(PillowImage.new("RGBA", (24, 24), "orange"), x=-80)
    friend = Sprite(PillowImage.new("RGBA", (24, 24), "skyblue"), x=80)
    stage.add(hero)
    stage.add(friend)
    dance = Message[None]("dance")

    @hero.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])
    def broadcast(event: Event[Sprite, GamepadPress]) -> Action:
        return stage.broadcast(dance)

    friend.on_broadcast(
        dance, Script(Sprite).glide_by(y=60, seconds=0.3).glide_by(y=-60, seconds=0.3)
    )
    stage.run()


if __name__ == "__main__":
    main()
