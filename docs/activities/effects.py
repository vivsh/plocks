"""A moving dinosaur that flashes and fades, plus a rainbow bird."""

from pathlib import Path

from plocks import Effect, GamepadButton, Image, Key, Sprite, Stage

assets = Path(__file__).resolve().parent / "assets"
stage = Stage(background="#152c45")
player = stage.gamepads[0]
player.map_key(Key.SPACE, GamepadButton.A)
player.map_key(Key.X, GamepadButton.B)
player.map_key(Key.C, GamepadButton.Y)

hero = Sprite(Image(assets / "dinosaur.png").resized(72, 72), x=-100, y=-40)
bird = Sprite(Image(assets / "bird.png").resized(56, 40), y=70)
stage.add(hero)
stage.add(bird)

# Walking and appearance are separate jobs, so fading doesn't stop the walk.
hero.on_start(hero.repeat().glide_by(x=200, seconds=2).glide_by(x=-200, seconds=2))
bird.on_start(bird.repeat().animate_effect(Effect.COLOR, to=200, seconds=3))

flash = (
    hero.sequence()
    .animate_effect(Effect.BRIGHTNESS, to=70, seconds=0.05)
    .animate_effect(Effect.BRIGHTNESS, to=0, seconds=0.2)
)
fade = (
    hero.sequence()
    .animate_effect(Effect.GHOST, to=100, seconds=0.7)
    .animate_effect(Effect.GHOST, to=0, seconds=0.7)
)
hero.on_button_down(GamepadButton.A, flash, gamepad=player)
hero.on_button_down(GamepadButton.B, fade, gamepad=player)
hero.on_button_down(GamepadButton.Y, hero.sequence().clear_effects(), gamepad=player)

if __name__ == "__main__":
    stage.run()
