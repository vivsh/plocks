"""Hold arrows to move; press Space for a short movement script."""

from pathlib import Path

from plocks import Ease, Event, GamepadButton, Image, Key, Sprite, Stage

assets = Path(__file__).resolve().parent / "assets"
stage = Stage(width=800, height=450, background="#fff0cc")

# Keys feed logical controls; gamepads and remote players work too.
stage.gamepads[0].map_left_stick(left=Key.LEFT, right=Key.RIGHT, up=Key.UP, down=Key.DOWN)
stage.gamepads[0].map_key(Key.LEFT, GamepadButton.LEFT)
stage.gamepads[0].map_key(Key.RIGHT, GamepadButton.RIGHT)
stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
dino = Sprite(Image(assets / "dinosaur.png").resized(width=72, height=72), y=-90)
stage.add(dino)
hop = dino.sequence()
hop.glide_by(y=90, seconds=0.3, easing=Ease.OUT)
hop.glide_by(y=-90, seconds=0.3, easing=Ease.IN)
dino.on_button_down(GamepadButton.A, hop, gamepad=stage.gamepads[0])


# A press is one event. An update checks held keys every game step.
@dino.on_update
def walk(event: Event[Sprite, float]) -> None:
    if stage.gamepads[0].left_stick[0] > 0:
        event.target.x += 160 * event.data
    if stage.gamepads[0].left_stick[0] < 0:
        event.target.x -= 160 * event.data


if __name__ == "__main__":
    stage.run()
