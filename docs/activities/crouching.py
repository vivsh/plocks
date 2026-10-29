"""Hold Down to duck, then walk out from under the ceiling to stand."""

from plocks import Anchor, BodyType, Event, GamepadButton, Image, Key, Sprite, Stage


def main() -> None:
    stage = Stage(physics=True, background="midnightblue")
    player = stage.gamepads[0]
    player.map_left_stick(left=Key.LEFT, right=Key.RIGHT)
    player.map_key(Key.DOWN, GamepadButton.DOWN)
    standing = Image.rectangle(24, 60, color="orange", anchor=Anchor.BOTTOM_CENTER)
    crouching = Image.rectangle(24, 24, color="gold", anchor=Anchor.BOTTOM_CENTER)
    hero = Sprite(standing, x=-160, y=-80)
    ground = Sprite(Image.rectangle(480, 20, color="seagreen"), y=-90, body_type=BodyType.STATIC)
    ceiling = Sprite(Image.rectangle(140, 20, color="skyblue"), y=-30, body_type=BodyType.STATIC)
    for actor in (ground, ceiling, hero):
        stage.add(actor)
    hero.body.rotation_locked = True

    @stage.on_update
    def update(event: Event[Stage, float]) -> None:
        # Keep vertical speed so gravity and landing still work.
        hero.body.velocity = (player.left_stick[0] * 120, hero.body.velocity[1])
        if player.is_down(GamepadButton.DOWN):
            if hero.image is not crouching:
                hero.image = crouching
        # Retry each update: we stand once there is enough room overhead.
        elif hero.image is not standing and hero.body.can_fit_image(standing):
            hero.image = standing

    stage.run()


if __name__ == "__main__":
    main()
