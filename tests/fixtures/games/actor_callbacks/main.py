"""Hold arrows to move the orange actor. Click an actor to trigger its behavior."""

from math import sin

from PIL import Image as PillowImage

from plocks import (
    Canvas,
    Click,
    Event,
    GamepadButton,
    GamepadPress,
    Key,
    Puppet,
    Script,
    Sprite,
    Stage,
)


def main() -> None:
    """Attach callbacks to actors; keep the score overlay and global clicks on Stage."""
    stage = Stage(width=640, height=360, background="midnightblue")
    stage.gamepads[0].map_key(Key.LEFT, GamepadButton.LEFT)
    stage.gamepads[0].map_key(Key.P, GamepadButton.START)
    stage.gamepads[0].map_key(Key.RIGHT, GamepadButton.RIGHT)
    hero = Sprite(PillowImage.new("RGBA", (40, 48), "orange"), x=-100)
    friend = Sprite(PillowImage.new("RGBA", (40, 40), "skyblue"), x=100)
    stage.add(hero)
    stage.add(friend)
    person = Puppet.stick_figure(color="lightgreen")
    person.position = (230, -20)
    stage.add(person)
    person.on_click(Script(Puppet).say("Puppet clicked!", seconds=0.6))
    clicks = 0

    @hero.on_update
    def move(event: Event[Sprite, float]) -> None:
        dt = event.data
        direction = int(stage.gamepads[0].is_down(GamepadButton.RIGHT)) - int(
            stage.gamepads[0].is_down(GamepadButton.LEFT)
        )
        hero.x = max(-280, min(280, hero.x + direction * 160 * dt))

    hero.on_click(
        Script(Sprite)
        .say("You clicked me!", seconds=0.4)
        .glide_by(y=40, seconds=0.2)
        .glide_by(y=-40, seconds=0.2)
    )

    @friend.on_update
    def patrol(event: Event[Sprite, float]) -> None:
        friend.x = 100 + sin(stage.time) * 40

    @friend.on_click
    def greet(event: Event[Sprite, Click]) -> None:
        _position, button = event.data
        friend.say(f"{button.name.title()} click!")

    @person.on_update
    def bob(event: Event[Puppet, float]) -> None:
        person.y = -20 + sin(stage.time * 1.5) * 8

    @stage.on_click
    def count_click(event: Event[Stage, Click]) -> None:
        _position, _button = event.data
        nonlocal clicks
        clicks += 1

    @stage.on_button_down(GamepadButton.START, gamepad=stage.gamepads[0])
    def pause(event: Event[Stage, GamepadPress]) -> None:
        if stage.paused:
            stage.resume()
        else:
            stage.pause()

    @stage.on_draw
    def draw(canvas: Canvas) -> None:
        canvas.text("Arrows: move orange. Click an actor.", (-295, 160), size=24)
        canvas.text(f"All stage clicks: {clicks}    P: pause/resume", (-295, -145), size=22)

    stage.run()


if __name__ == "__main__":
    main()
