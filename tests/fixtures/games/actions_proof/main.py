"""Press Space for chained actions; A demonstrates the same actions with reusable Scripts."""

from PIL import Image

from plocks import Action, Event, Key, Script, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (32, 40), "orange"), y=-100)
    friend = Sprite(Image.new("RGBA", (28, 28), "skyblue"), x=-150, y=60)
    stage.add(hero)
    stage.add(friend)

    @hero.on_key_down(Key.SPACE)
    def climb(event: Event[Sprite, Key]) -> Action:
        first = hero.glide_by(y=50, seconds=0.3)
        return hero.glide_by(y=50, seconds=0.3, after=first)

    @hero.on_key_down(Key.A)
    def descend(event: Event[Sprite, Key]) -> Script[Sprite]:
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
