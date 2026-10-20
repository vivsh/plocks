from PIL import Image as PillowImage

from plocks import Image, Script, Sprite, Stage


def main() -> None:
    """One behavior owns both walking and its changing images."""
    stage = Stage()
    frames = tuple(
        Image(PillowImage.new("RGBA", (24, 32), color)) for color in ("orange", "gold", "tomato")
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
                    meanwhile=Script(Sprite).repeat().call(Script(Sprite).images(frames, fps=8)),
                )
            )
            .call(
                Script(Sprite).during(
                    Script(Sprite).glide_to(x=-150, seconds=2),
                    meanwhile=Script(Sprite).repeat().call(Script(Sprite).images(frames, fps=8)),
                )
            )
        )
    )
    stage.run()


if __name__ == "__main__":
    main()
