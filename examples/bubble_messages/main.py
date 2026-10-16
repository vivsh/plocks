from PIL import Image

from plocks import Action, Key, Message, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    hero = Sprite(Image.new("RGBA", (24, 24), "orange"), x=-80)
    friend = Sprite(Image.new("RGBA", (24, 24), "skyblue"), x=80)
    stage.add(hero)
    stage.add(friend)
    score_added = Message[int]("score added")
    score = 0

    @hero.on_message(score_added)
    def add_score(amount: int) -> None:
        nonlocal score
        score += amount
        hero.say(f"Score: {score}", seconds=1)

    @hero.on_key_down(Key.SPACE)
    def collect() -> Action:
        return stage.broadcast(score_added, 1)

    stage.run()


if __name__ == "__main__":
    main()
