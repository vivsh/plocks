"""Bubble controls."""

from PIL import Image as PillowImage

from plocks import Event, GamepadButton, GamepadPress, Key, Script, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    stage.gamepads[0].map_key(Key.C, GamepadButton.X)
    stage.gamepads[0].map_key(Key.ESCAPE, GamepadButton.START)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    hero = Sprite(PillowImage.new("RGBA", (32, 40), "orange"))
    stage.add(hero)
    hero.say("Press Space to think; C to clear.")

    @stage.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])
    def wonder(event: Event[Stage, GamepadPress]) -> None:
        hero.think("What shall we make?")

    @stage.on_button_down(GamepadButton.X, gamepad=stage.gamepads[0])
    def clear(event: Event[Stage, GamepadPress]) -> None:
        hero.clear_bubble()

    hero.on_button_down(
        GamepadButton.START, Script(Sprite).clear_bubble(), gamepad=stage.gamepads[0]
    )
    stage.run()


if __name__ == "__main__":
    main()
