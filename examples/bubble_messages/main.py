"""Bubble messages."""

from PIL import Image

from plocks import Broadcast, Key, Message, Say, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue", bubble_text_size=28)
    hero = Sprite(Image.new("RGBA", (32, 40), "orange"))
    stage.add(hero)
    score_added = Message[int]("score added")
    score = 0

    @stage.on_message(score_added)
    def show_score(amount: int) -> None:
        nonlocal score
        score += amount
        hero.act(Say(f"Score: {score}", seconds=2))

    stage.on_key_down(Key.SPACE, hero, Broadcast(score_added, 1))
    stage.run()


if __name__ == "__main__":
    main()
