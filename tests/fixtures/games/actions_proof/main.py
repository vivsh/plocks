"""Press Space for chained actions; A demonstrates the same actions with await."""

from PIL import Image

from plocks import Action, Key, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (32, 40), "orange"), y=-100)
    friend = Sprite(Image.new("RGBA", (28, 28), "skyblue"), x=-150, y=60)
    stage.add(hero)
    stage.add(friend)

    @hero.on_key_down(Key.SPACE)
    def climb() -> Action:
        first = hero.glide_by(y=50, seconds=0.3)
        return hero.glide_by(y=50, seconds=0.3, after=first)

    @hero.on_key_down(Key.A)
    async def descend() -> None:
        await hero.glide_by(y=-50, seconds=0.3)
        await hero.glide_by(y=-50, seconds=0.3)

    @friend.on_update
    def patrol(dt: float) -> None:
        friend.x += 60 * dt
        if friend.x > 200:
            friend.x = -200

    stage.run()


if __name__ == "__main__":
    main()
