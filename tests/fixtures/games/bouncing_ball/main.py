"""A ball falling and bouncing, with no update callback or manual motion."""

from PIL import Image as PillowImage
from PIL import ImageDraw

from plocks import BodyType, Circle, Sprite, Stage


def main() -> None:
    stage = Stage(physics=True, background="midnightblue")

    picture = PillowImage.new("RGBA", (40, 40))
    ImageDraw.Draw(picture).ellipse((0, 0, 39, 39), fill="orange")

    ball = Sprite(picture, y=100)
    floor = Sprite(
        PillowImage.new("RGBA", (480, 20), "white"),
        y=-150,
        body_type=BodyType.STATIC,
    )
    stage.add(ball)
    stage.add(floor)

    ball.body.shape = Circle(20)
    ball.body.bounce = floor.body.bounce = 1

    stage.run()


if __name__ == "__main__":
    main()
