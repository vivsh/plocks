"""Scripts: conditions, together/then, reuse, speech and cancellation."""

from pathlib import Path

from plocks import (
    Ease,
    Event,
    GamepadButton,
    GamepadDown,
    GamepadPress,
    Image,
    Key,
    Sprite,
    Stage,
)

assets = Path(__file__).resolve().parents[1] / "assets"
stage = Stage(background="#fff0cc")

# Player one already has Space for jumping; map extra controls here.
player = stage.gamepads[0]
player.map_key(Key.H, GamepadButton.Y)
player.map_key(Key.R, GamepadButton.SELECT)
player.map_key(Key.UP, GamepadButton.UP)
hero = Sprite(Image(assets / "dinosaur.png").resized(width=72, height=72), x=-120)
stage.add(hero)
trip = hero.sequence().glide_to(x=120, seconds=1, easing=Ease.IN_OUT)
chat = hero.repeat().say("Coming through!", seconds=0.4).think("Whee!", seconds=0.4)
together = hero.sequence().during(trip, meanwhile=chat)
yes = hero.sequence().say("You held Up!", seconds=1)
no = hero.sequence().say("Try holding Up next time.", seconds=1)
outing = (
    hero.sequence()
    .call(together)
    .when(GamepadDown(GamepadButton.UP, gamepad=player), then=yes, either=no)
)
hero.on_button_down(GamepadButton.A, outing, gamepad=player)


@hero.on_button_down(GamepadButton.SELECT, gamepad=player)
def return_home(event: Event[Sprite, GamepadPress]) -> None:
    # stop cancels this character's work. Properties change immediately.
    event.target.stop()
    event.target.position = (-120, 0)
    event.target.clear_bubble()


@hero.on_button_down(GamepadButton.Y, gamepad=player)
def hop(event: Event[Sprite, GamepadPress]) -> None:
    # after connects commands without a separate script or timer.
    up = event.target.glide_by(y=80, seconds=0.3, easing=Ease.OUT)
    event.target.glide_by(y=-80, seconds=0.3, easing=Ease.IN, after=up)


if __name__ == "__main__":
    stage.run()
