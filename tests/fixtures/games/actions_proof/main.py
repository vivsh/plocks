"""Press Space for chained actions; A demonstrates the same actions with reusable Scripts."""

from PIL import Image as PillowImage

from plocks import Action, Event, GamepadButton, GamepadPress, Key, Script, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    stage.gamepads[0].map_key(Key.A, GamepadButton.LEFT)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    hero = Sprite(PillowImage.new("RGBA", (32, 40), "orange"), y=-100)
    friend = Sprite(PillowImage.new("RGBA", (28, 28), "skyblue"), x=-150, y=60)
    stage.add(hero)
    stage.add(friend)

    @hero.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])
    def climb(event: Event[Sprite, GamepadPress]) -> Action:
        first = hero.glide_by(y=50, seconds=0.3)
        return hero.glide_by(y=50, seconds=0.3, after=first)

    @hero.on_button_down(GamepadButton.LEFT, gamepad=stage.gamepads[0])
    def descend(event: Event[Sprite, GamepadPress]) -> Script[Sprite]:
        return Script(Sprite).glide_by(y=-50, seconds=0.3).glide_by(y=-50, seconds=0.3)

    @friend.on_update
    def patrol(event: Event[Sprite, float]) -> None:
        dt = event.data
        friend.x += 60 * dt
        if friend.x > 200:
            friend.x = -200

    stage.run()


if __name__ == "__main__":
    main()
