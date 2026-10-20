from PIL import Image as PillowImage

from plocks import GamepadButton, Key, Script, Sprite, Stage


def main() -> None:
    """Press Right to glide. Repeated presses wait until the current glide finishes."""
    stage = Stage()
    stage.gamepads[0].map_key(Key.RIGHT, GamepadButton.RIGHT)
    cat = Sprite(PillowImage.new("RGBA", (32, 32), "orange"))
    stage.add(cat)
    cat.on_button_down(
        GamepadButton.RIGHT, Script(Sprite).glide_by(x=60, seconds=0.4), gamepad=stage.gamepads[0]
    )
    stage.run()


if __name__ == "__main__":
    main()
