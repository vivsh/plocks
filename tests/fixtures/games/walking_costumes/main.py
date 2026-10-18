from PIL import Image

from plocks import Costume, Script, Sprite, Stage


def main() -> None:
    """One behavior owns both walking and its changing costumes."""
    stage = Stage()
    frames = tuple(
        Costume(Image.new("RGBA", (24, 32), color)) for color in ("orange", "gold", "tomato")
    )
    hero = Sprite(frames[0], x=-150)
    stage.add(hero)
    hero.act(
        Script(Sprite)
        .repeat()
        .call(
            Script(Sprite)
            .call(
                Script(Sprite).during(
                    Script(Sprite).glide_to(x=150, seconds=2),
                    meanwhile=Script(Sprite).repeat().call(Script(Sprite).costumes(frames, fps=8)),
                )
            )
            .call(
                Script(Sprite).during(
                    Script(Sprite).glide_to(x=-150, seconds=2),
                    meanwhile=Script(Sprite).repeat().call(Script(Sprite).costumes(frames, fps=8)),
                )
            )
        )
    )
    stage.run()


if __name__ == "__main__":
    main()
