from PIL import Image

from plocks import Action, Key, Message, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (24, 24), "orange"), x=-80)
    friend = Sprite(Image.new("RGBA", (24, 24), "skyblue"), x=80)
    stage.add(hero)
    stage.add(friend)
    push = Message[int]("push")

    @friend.on_message(push)
    def recoil(distance: int) -> Action:
        out = friend.glide_by(x=distance, seconds=0.1)
        return friend.glide_by(x=-distance, seconds=0.2, after=out)

    @hero.on_key_down(Key.H)
    def hit() -> Action:
        return stage.broadcast(push, 20)

    stage.run()


if __name__ == "__main__":
    main()
