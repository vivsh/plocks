from PIL import Image as PillowImage

from plocks import Action, Event, GamepadButton, GamepadPress, Key, Message, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    stage.gamepads[0].map_key(Key.H, GamepadButton.Y)
    hero = Sprite(PillowImage.new("RGBA", (24, 24), "orange"), x=-80)
    friend = Sprite(PillowImage.new("RGBA", (24, 24), "skyblue"), x=80)
    stage.add(hero)
    stage.add(friend)
    push = Message[int]("push")

    @friend.on_broadcast(push)
    def recoil(event: Event[Sprite, int]) -> Action:
        distance = event.data
        out = friend.glide_by(x=distance, seconds=0.1)
        return friend.glide_by(x=-distance, seconds=0.2, after=out)

    @hero.on_button_down(GamepadButton.Y, gamepad=stage.gamepads[0])
    def hit(event: Event[Sprite, GamepadPress]) -> Action:
        return stage.broadcast(push, 20)

    stage.run()


if __name__ == "__main__":
    main()
