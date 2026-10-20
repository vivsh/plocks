"""Exercise clone controls, initialization, landing and cleanup on a native window."""

import json
import sys
from dataclasses import dataclass
from importlib.resources import as_file, files

import pygame

from plocks import (
    Body,
    BodyType,
    Box,
    Canvas,
    Event,
    GamepadButton,
    GamepadPress,
    Image,
    Key,
    Sprite,
    Stage,
)


@dataclass
class Health:
    health: int = 10


def main() -> None:
    """Play a bounded input-driven physical clone scene and optionally save its image."""
    stage = Stage(width=640, height=400, physics=True, background="#22364d")
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    stage.physics.gravity = (0, -500)
    # Asset paths come from the installed package, including in the wheel proof.
    with as_file(files("plocks").joinpath("_games/platformer/assets/hero.png")) as image:
        source = Sprite(image, x=-230, y=50, state=Health)
    with as_file(files("plocks").joinpath("_games/platformer/assets/platform.png")) as image:
        ground = Image(image).resized(width=620, height=12)
    floor = Sprite(ground, y=-130, body_type=BodyType.STATIC)
    stage.add(source)
    stage.add(floor)
    floor.body.shape = Box(620, 12)
    source.body.shape = Box(16, 28)
    source.body.mass = 2
    source.body.rotation_locked = True
    copies: list[Sprite[Health]] = []
    bodies: list[Body] = []
    births: list[Sprite[Health]] = []
    frames = 0
    driver = ""
    focus_restores = 0

    @source.on_clone
    def initialize(event: Event[Sprite[Health], None]) -> None:
        assert event.source is source and event.target in copies
        event.target.state.health = 3
        event.target.say("Clone!", seconds=0.6)
        births.append(event.target)

    @stage.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])
    def spawn(event: Event[Stage, GamepadPress]) -> None:
        assert not copies
        for x in (-80, 70, 220):
            clone = source.clone()
            assert clone.body.velocity == (0, 0)
            clone.position = (x, 90)
            copies.append(clone)
            bodies.append(clone.body)
        assert not births

    @stage.on_update
    def exercise(event: Event[Stage, float]) -> None:
        tick = round(stage.time * 60)
        if tick == 8:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        if tick == 25:
            assert len(copies) == len(births) == 3 and source.state.health == 10
            assert all(clone.state.health == 3 for clone in copies)
        if tick == 100:
            assert source.body.grounded and all(clone.body.grounded for clone in copies)
            copies[0].body.impulse(y=400)
        if tick == 110:
            assert copies[0].y > copies[1].y + 20
            assert not copies[0].body.grounded and copies[1].body.grounded

    @stage.on_draw
    def overlay(canvas: Canvas) -> None:
        nonlocal frames, driver, focus_restores
        frames += 1
        # Keep this automated window test progressing if another terminal takes focus.
        # The production suspension policy is unchanged; pause tests cover that separately.
        if stage._pause_reasons == {"focus"}:
            focus_restores += 1
            pygame.event.post(pygame.event.Event(pygame.WINDOWFOCUSGAINED))
        canvas.text("Original + 3 independent physical clones", (-300, 177), size=23)
        canvas.text("Clones copy health, handlers, shapes and materials.", (-300, -175), size=19)
        for actor in (source, *copies):
            name = "Clone" if actor.is_clone else "Original"
            canvas.text(f"{name}: {actor.state.health}", (actor.x - 40, actor.y + 30), size=18)
        if stage.time >= 2:
            assert len(births) == 3
            driver = pygame.display.get_driver()
            if len(sys.argv) > 1:
                assert stage._target is not None
                pygame.image.save(stage._target, sys.argv[1])
            stage.stop()
        if frames > 600:
            raise AssertionError(f"Native clone scene did not advance: {stage._pause_reasons}")

    stage.run()
    assert driver
    assert not stage.objects and not stage._actions and not stage._pending
    assert not stage._clone_handlers and not stage.physics._bodies and not stage._voices
    assert stage._target is None and all(body._native is None for body in bodies)
    assert all(actor._stage is None for actor in (source, *copies))
    print(
        "NATIVE_CLONES_OK",
        json.dumps(
            {
                "driver": driver,
                "clones": len(copies),
                "frames": frames,
                "synthetic_focus_restores": focus_restores,
            }
        ),
    )


if __name__ == "__main__":
    main()
