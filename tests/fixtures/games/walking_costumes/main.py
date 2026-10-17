from PIL import Image

from plocks import Costume, Sprite, Stage


def main() -> None:
    """One behavior owns both walking and its changing costumes."""
    stage = Stage()
    frames = tuple(
        Costume(Image.new("RGBA", (24, 32), color)) for color in ("orange", "gold", "tomato")
    )
    hero = Sprite(frames[0], x=-150)
    stage.add(hero)
    hero.act(
        hero.repeat().act(
            hero.sequence()
            .act(
                hero.sequence().during(
                    hero.sequence().glide_to(x=150, seconds=2),
                    meanwhile=hero.repeat().act(hero.sequence().costumes(frames, fps=8)),
                )
            )
            .act(
                hero.sequence().during(
                    hero.sequence().glide_to(x=-150, seconds=2),
                    meanwhile=hero.repeat().act(hero.sequence().costumes(frames, fps=8)),
                )
            )
        )
    )
    stage.run()


if __name__ == "__main__":
    main()
