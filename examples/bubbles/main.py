"""Space: speak while walking. T: Puppet thought. P: pause/resume. C: stop the walk and speech."""

from PIL import Image

from plocks import During, GlideBy, Key, Puppet, Say, Sprite, Stage, Think


def main() -> None:
    """Dialogue and movement share one behavior; the friend updates independently."""
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (32, 40), "orange"), x=-100, y=-20)
    friend = Sprite(Image.new("RGBA", (28, 28), "skyblue"), x=-160, y=-100)
    stage.add(hero)
    stage.add(friend)
    person = Puppet.stick_figure(color="lightgreen")
    person.position = (145, 15)
    stage.add(person)
    stage.on_key_down(Key.T, person, Think("Where next?", seconds=2))
    stage.on_key_down(
        Key.SPACE,
        hero,
        During(
            GlideBy(x=100, seconds=1),
            meanwhile=Say("Watch me walk!", seconds=1),
        ),
    )

    @stage.on_key_down(Key.P)
    def pause() -> None:
        if stage.paused:
            stage.resume()
        else:
            stage.pause()

    @stage.on_key_down(Key.C)
    def cancel() -> None:
        hero.stop()

    @stage.on_update
    def update(dt: float) -> None:
        friend.x += 30 * dt
        if friend.x > 200:
            friend.x = -200

    stage.run()


if __name__ == "__main__":
    main()
