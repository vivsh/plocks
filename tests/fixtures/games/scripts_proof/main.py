"""One reusable definition, two independent targets, and synchronous events."""

from pathlib import Path

from plocks import (
    Canvas,
    Event,
    GamepadButton,
    GamepadDown,
    GamepadPress,
    Key,
    Message,
    Script,
    Sprite,
    Stage,
)

assets = Path("assets").resolve()
stage = Stage(background="#172d46")
stage.gamepads[0].map_key(Key.P, GamepadButton.START)
stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
stage.gamepads[0].map_key(Key.UP, GamepadButton.UP)
first = Sprite(assets / "hero.png", x=-120, y=-40)
second = Sprite(assets / "hero.png", x=40, y=40)
stage.add(first)
stage.add(second)
arrived = Message[int]("arrived")
arrivals: list[Sprite] = []
trip = (
    first.sequence()
    .when(
        GamepadDown(GamepadButton.UP, gamepad=stage.gamepads[0]),
        then=Script().glide_by(y=60, seconds=0.5),
        either=Script().glide_by(x=60, seconds=0.5),
    )
    .broadcast(arrived, 1)
)


@first.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])
def start_trip(event: Event[Sprite, GamepadPress]) -> Script[Sprite]:
    assert event.target is first and event.source is stage and event.data.button is GamepadButton.A
    return trip


second.on_button_down(GamepadButton.A, trip, gamepad=stage.gamepads[0])


@stage.on_broadcast(arrived)
def report(event: Event[Stage, int]) -> None:
    assert isinstance(event, Event) and event.target is stage and event.data == 1
    if isinstance(event.source, Sprite):
        arrivals.append(event.source)


@first.on_broadcast(arrived)
def receive(event: Event[Sprite, int]) -> None:
    assert isinstance(event, Event) and event.target is first and event.source in (first, second)


@stage.on_update
def check_update(event: Event[Stage, float]) -> None:
    assert event.target is stage and event.source is stage
    assert event.data == 1 / stage.tick_rate


@stage.on_button_down(GamepadButton.START, gamepad=stage.gamepads[0])
def pause(event: Event[Stage, GamepadPress]) -> None:
    if stage.paused:
        stage.resume()
    else:
        stage.pause()


@stage.on_draw
def draw(canvas: Canvas) -> None:
    canvas.text("SPACE: shared trip   UP: choose vertical   P: pause", (-225, 140), size=18)


if __name__ == "__main__":
    stage.run()
