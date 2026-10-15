"""Space starts a glide while a second actor keeps moving; A uses an async handler."""

from PIL import Image

from plocks import Ease, GlideBy, Key, Sprite, Stage

stage = Stage(background="midnightblue")
hero = Sprite(Image.new("RGBA", (32, 32), "orange"), y=-100)
friend = Sprite(Image.new("RGBA", (24, 24), "skyblue"), x=-150, y=80)
stage.add(hero)
stage.add(friend)
hero.on_key_down(Key.SPACE, GlideBy(y=100, seconds=0.6, easing=Ease.OUT))


@stage.on_key_down(Key.A)
async def descend() -> None:
    await hero.glide_by(y=-100, seconds=0.6)


@stage.on_key_down(Key.P)
def pause() -> None:
    if stage.paused:
        stage.resume()
    else:
        stage.pause()


@friend.on_update
def update(dt: float) -> None:
    friend.x += 40 * dt
    if friend.x > 180:
        friend.x = -180


stage.run()
