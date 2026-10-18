"""Hold arrows to move; press Space for a short movement script."""

from pathlib import Path

from plocks import Costume, Ease, Event, Key, Sprite, Stage

assets = Path(__file__).resolve().parent / "assets"
stage = Stage(width=800, height=450, background="#fff0cc")
dino = Sprite(Costume(assets / "dinosaur.png").resized(width=72, height=72), y=-90)
stage.add(dino)
hop = dino.sequence()
hop.glide_by(y=90, seconds=0.3, easing=Ease.OUT)
hop.glide_by(y=-90, seconds=0.3, easing=Ease.IN)
dino.on_key_down(Key.SPACE, hop)


# A press is one event. An update checks held keys every game step.
@dino.on_update
def walk(event: Event[Sprite, float]) -> None:
    if stage.keyboard.is_down(Key.RIGHT):
        event.target.x += 160 * event.data
    if stage.keyboard.is_down(Key.LEFT):
        event.target.x -= 160 * event.data


if __name__ == "__main__":
    stage.run()
