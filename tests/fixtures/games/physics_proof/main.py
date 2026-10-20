"""Space applies a physical impulse; the other actor keeps following a script."""

from PIL import Image as PillowImage

from plocks import (
    Action,
    BodyType,
    Event,
    GamepadButton,
    GamepadPress,
    Key,
    Script,
    Sprite,
    Stage,
    TileMap,
)


def main() -> None:
    stage = Stage(physics=True, background="midnightblue")
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    floor = TileMap(
        ["##########"],
        {"#": PillowImage.new("RGBA", (32, 32), "forestgreen")},
        tile_size=(32, 32),
        solid={"#"},
        x=-160,
        y=-100,
    )
    hero = Sprite(PillowImage.new("RGBA", (20, 20), "orange"), y=20)
    friend = Sprite(
        PillowImage.new("RGBA", (20, 20), "skyblue"), x=-100, y=80, body_type=BodyType.NONE
    )
    stage.add(floor)
    stage.add(hero)
    stage.add(friend)
    hero.body.rotation_locked = True
    friend.on_start(Script(Sprite).repeat().glide_to(x=100, seconds=1).glide_to(x=-100, seconds=1))

    @hero.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])
    def jump(event: Event[Sprite, GamepadPress]) -> Action | None:
        if hero.body.grounded:
            impulse = hero.body.impulse(y=350)
            return hero.say("Jump!", seconds=0.4, after=impulse)
        return None

    stage.run()


if __name__ == "__main__":
    main()
