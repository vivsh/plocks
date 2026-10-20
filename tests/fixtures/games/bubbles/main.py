"""Space: speak while walking. T: Puppet thought. P: pause/resume. C: stop the walk and speech."""

from PIL import Image as PillowImage

from plocks import Event, GamepadButton, GamepadPress, Key, Puppet, Script, Sprite, Stage


def main() -> None:
    """Dialogue and movement share one behavior; the friend updates independently."""
    stage = Stage(background="midnightblue")
    stage.gamepads[0].map_key(Key.C, GamepadButton.X)
    stage.gamepads[0].map_key(Key.P, GamepadButton.START)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    stage.gamepads[0].map_key(Key.T, GamepadButton.SELECT)
    hero = Sprite(PillowImage.new("RGBA", (32, 40), "orange"), x=-100, y=-20)
    friend = Sprite(PillowImage.new("RGBA", (28, 28), "skyblue"), x=-160, y=-100)
    stage.add(hero)
    stage.add(friend)
    person = Puppet.stick_figure(color="lightgreen")
    person.position = (145, 15)
    stage.add(person)
    person.on_button_down(
        GamepadButton.SELECT,
        Script(Puppet).think("Where next?", seconds=2),
        gamepad=stage.gamepads[0],
    )
    hero.on_button_down(
        GamepadButton.A,
        Script(Sprite).during(
            Script(Sprite).glide_by(x=100, seconds=1),
            meanwhile=Script(Sprite).say("Watch me walk!", seconds=1),
        ),
        gamepad=stage.gamepads[0],
    )

    @stage.on_button_down(GamepadButton.START, gamepad=stage.gamepads[0])
    def pause(event: Event[Stage, GamepadPress]) -> None:
        if stage.paused:
            stage.resume()
        else:
            stage.pause()

    @stage.on_button_down(GamepadButton.X, gamepad=stage.gamepads[0])
    def cancel(event: Event[Stage, GamepadPress]) -> None:
        hero.stop()

    @friend.on_update
    def update(event: Event[Sprite, float]) -> None:
        dt = event.data
        friend.x += 30 * dt
        if friend.x > 200:
            friend.x = -200

    stage.run()


if __name__ == "__main__":
    main()
