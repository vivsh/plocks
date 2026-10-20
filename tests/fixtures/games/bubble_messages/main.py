from PIL import Image as PillowImage

from plocks import Action, Event, GamepadButton, GamepadPress, Key, Message, Sprite, Stage


def main() -> None:
    stage = Stage(background="midnightblue")
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    hero = Sprite(PillowImage.new("RGBA", (24, 24), "orange"), x=-80)
    friend = Sprite(PillowImage.new("RGBA", (24, 24), "skyblue"), x=80)
    stage.add(hero)
    stage.add(friend)
    score_added = Message[int]("score added")
    score = 0

    @hero.on_broadcast(score_added)
    def add_score(event: Event[Sprite, int]) -> None:
        amount = event.data
        nonlocal score
        score += amount
        hero.say(f"Score: {score}", seconds=1)

    @hero.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])
    def collect(event: Event[Sprite, GamepadPress]) -> Action:
        return stage.broadcast(score_added, 1)

    stage.run()


if __name__ == "__main__":
    main()
