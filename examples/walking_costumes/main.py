"""One behavior owns both walking and its changing costumes."""

from PIL import Image

from plocks import Costume, Costumes, During, GlideTo, Loop, Sequence, Sprite, Stage

stage = Stage()
frames = tuple(
    Costume(Image.new("RGBA", (24, 32), color)) for color in ("orange", "gold", "tomato")
)
hero = Sprite(frames[0], x=-150)
stage.add(hero)
hero.act(
    Loop(
        Sequence(
            During(GlideTo(x=150, seconds=2), meanwhile=Loop(Costumes(frames, fps=8))),
            During(GlideTo(x=-150, seconds=2), meanwhile=Loop(Costumes(frames, fps=8))),
        )
    )
)
stage.run()
