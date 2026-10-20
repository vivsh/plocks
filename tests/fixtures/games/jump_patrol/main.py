from PIL import Image as PillowImage

from plocks import Ease, GamepadButton, Image, Key, Script, Sprite, Stage


def main() -> None:
    """Space jumps while a friend patrols independently; no timers or flags."""
    stage = Stage(background="midnightblue")
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    idle = Image(PillowImage.new("RGBA", (32, 40), "orange"))
    jumping = Image(PillowImage.new("RGBA", (32, 40), "gold"))
    hero = Sprite(idle, y=-100)
    friend = Sprite(PillowImage.new("RGBA", (28, 28), "skyblue"), x=-150, y=60)
    stage.add(hero)
    stage.add(friend)
    hero.on_button_down(
        GamepadButton.A,
        Script(Sprite)
        .set_image(jumping)
        .glide_by(y=100, seconds=0.3, easing=Ease.OUT)
        .glide_by(y=-100, seconds=0.3, easing=Ease.IN)
        .set_image(idle),
        gamepad=stage.gamepads[0],
    )
    friend.on_start(
        Script(Sprite)
        .repeat()
        .call(
            Script(Sprite)
            .glide_to(x=150, seconds=1.5)
            .wait(0.2)
            .glide_to(x=-150, seconds=1.5)
            .wait(0.2)
        )
    )
    stage.run()


if __name__ == "__main__":
    main()
