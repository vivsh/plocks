"""Hold arrows to move the orange actor. Click an actor to trigger its behavior."""

from math import sin

from PIL import Image

from plocks import Canvas, Key, MouseButton, Point, Puppet, Sprite, Stage


def main() -> None:
    """Attach callbacks to actors; keep the score overlay and global clicks on Stage."""
    stage = Stage(width=640, height=360, background="midnightblue")
    hero = Sprite(Image.new("RGBA", (40, 48), "orange"), x=-100)
    friend = Sprite(Image.new("RGBA", (40, 40), "skyblue"), x=100)
    stage.add(hero)
    stage.add(friend)
    person = Puppet.stick_figure(color="lightgreen")
    person.position = (230, -20)
    stage.add(person)
    person.on_click(person.sequence().say("Puppet clicked!", seconds=0.6))
    clicks = 0

    @hero.on_update
    def move(dt: float) -> None:
        direction = int(stage.keyboard.is_down(Key.RIGHT)) - int(stage.keyboard.is_down(Key.LEFT))
        hero.x = max(-280, min(280, hero.x + direction * 160 * dt))

    hero.on_click(
        hero.sequence()
        .say("You clicked me!", seconds=0.4)
        .glide_by(y=40, seconds=0.2)
        .glide_by(y=-40, seconds=0.2)
    )

    @friend.on_update
    def patrol(dt: float) -> None:
        friend.x = 100 + sin(stage.time) * 40

    @friend.on_click
    def greet(position: Point, button: MouseButton) -> None:
        friend.say(f"{button.name.title()} click!")

    @person.on_update
    def bob(dt: float) -> None:
        person.y = -20 + sin(stage.time * 1.5) * 8

    @stage.on_click
    def count_click(position: Point, button: MouseButton) -> None:
        nonlocal clicks
        clicks += 1

    @stage.on_key_down(Key.P)
    def pause() -> None:
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
