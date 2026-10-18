"""Walk, jump onto solid platforms, ride a lift, and spin a crate with torque."""

from PIL import Image

from plocks import Action, BodyType, Canvas, Event, Key, Script, Sprite, Stage, TileMap


def main() -> None:
    stage = Stage(width=640, height=360, physics=True, background="midnightblue")
    ground = Image.new("RGBA", (32, 32), "forestgreen")
    stone = Image.new("RGBA", (32, 32), "slategray")
    world = TileMap(
        [
            "....................",
            "..............###...",
            "....................",
            "......###...........",
            "....................",
            "....................",
            "GGGGGGGGGGGGGGGGGGGG",
        ],
        {"G": ground, "#": stone},
        tile_size=(32, 32),
        solid={"G", "#"},
        x=-320,
        y=50,
    )
    stage.add(world)
    hero = Sprite(Image.new("RGBA", (24, 32), "orange"), x=-260, y=-100)
    lift = Sprite(
        Image.new("RGBA", (70, 12), "skyblue"), x=20, y=-100, body_type=BodyType.KINEMATIC
    )
    crate = Sprite(Image.new("RGBA", (28, 28), "gold"), x=210, y=100)
    stage.add(hero)
    stage.add(lift)
    stage.add(crate)
    hero.body.rotation_locked = True
    lift.on_start(Script(Sprite).repeat().glide_to(y=60, seconds=2).glide_to(y=-100, seconds=2))

    @hero.on_update
    def walk(event: Event[Sprite, float]) -> None:
        direction = int(stage.keyboard.is_down(Key.RIGHT)) - int(stage.keyboard.is_down(Key.LEFT))
        _, vertical = hero.body.velocity
        hero.body.velocity = (direction * 150, vertical)
        if hero.y < -250:
            hero.position = (-260, -100)
            hero.body.velocity = (0, 0)

    @hero.on_key_down(Key.SPACE)
    def jump(event: Event[Sprite, Key]) -> Action | None:
        if hero.body.grounded:
            return hero.body.impulse(y=400)
        return None

    @crate.on_key_down(Key.T)
    def spin(event: Event[Sprite, Key]) -> Action:
        return crate.body.torque(60000, seconds=0.3)

    @stage.on_draw
    def instructions(canvas: Canvas) -> None:
        canvas.text("Arrows: walk   Space: jump   T: spin crate", (-305, 160), size=22)
        canvas.text("Ride the blue lift. Platforms are solid on every side.", (-305, 133), size=18)

    stage.run()


if __name__ == "__main__":
    main()
