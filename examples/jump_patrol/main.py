"""Space jumps while a friend patrols independently; no timers or flags."""

from PIL import Image

from plocks import (
    Costume,
    Ease,
    GlideBy,
    GlideTo,
    Key,
    Loop,
    Sequence,
    SetCostume,
    Sprite,
    Stage,
    Wait,
)

stage = Stage(background="midnightblue")
idle = Costume(Image.new("RGBA", (32, 40), "orange"))
jumping = Costume(Image.new("RGBA", (32, 40), "gold"))
hero = Sprite(idle, y=-100)
friend = Sprite(Image.new("RGBA", (28, 28), "skyblue"), x=-150, y=60)
stage.add(hero)
stage.add(friend)
jump = Sequence(
    SetCostume(jumping),
    GlideBy(y=100, seconds=0.3, easing=Ease.OUT),
    GlideBy(y=-100, seconds=0.3, easing=Ease.IN),
    SetCostume(idle),
)
patrol = Loop(
    Sequence(GlideTo(x=150, seconds=1.5), Wait(0.2), GlideTo(x=-150, seconds=1.5), Wait(0.2))
)
stage.on_key_down(Key.SPACE, hero, jump)
stage.on_start(friend, patrol)
stage.run()
