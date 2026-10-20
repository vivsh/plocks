"""Swing Lab: a physical rope, one ball, and a safe landing."""

from pathlib import Path

from plocks import (
    BodyType,
    Button,
    Canvas,
    Circle,
    Event,
    GamepadButton,
    GamepadPress,
    Image,
    Key,
    Label,
    Sprite,
    Stage,
)

assets = Path(__file__).resolve().parent / "assets"
stage = Stage(width=640, height=400, physics=True, background="#172536")
stage.physics.gravity = (0, -500)
stage.gamepads[0].map_key(Key.R, GamepadButton.B)
ball = Sprite(Image(assets / "ball.png").resized(32, 32), x=80, y=-20)
floor = Sprite(Image(assets / "beam.png").resized(620, 20), y=-170, body_type=BodyType.STATIC)
stage.add(ball)
stage.add(floor)
ball.body.shape = Circle(16)
rope = stage.physics.rope((0, 100), ball, length=150)
hint = Label("Space: cut the rope. R: try again.", position=(0, 170))
cut = Button("Cut rope", position=(210, -120))
stage.add(hint)
stage.add(cut)


@stage.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])
def release(event: Event[Stage, GamepadPress]) -> None:
    rope.disconnect()


@cut.on_click
def click_cut(event: Event[Button, None]) -> None:
    rope.disconnect()
    stage.focus(None)


@stage.on_button_down(GamepadButton.B, gamepad=stage.gamepads[0])
def reset(event: Event[Stage, GamepadPress]) -> None:
    global rope
    # Remove the old link before moving the ball back to its starting place.
    rope.disconnect()
    ball.position = (80, -20)
    ball.body.velocity = (0, 0)
    ball.body.angular_velocity = 0
    rope = stage.physics.rope((0, 100), ball, length=150)


@stage.on_draw
def draw(canvas: Canvas) -> None:
    canvas.connection(rope, color="#ffe09a", width=3)
    canvas.circle((0, 100), 6, color="#ffe09a")


if __name__ == "__main__":
    stage.run()
