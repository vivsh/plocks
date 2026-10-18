from PIL import Image

from plocks import Key, Script, Sprite, Stage


def main() -> None:
    """Press Right to glide. Repeated presses wait until the current glide finishes."""
    stage = Stage()
    cat = Sprite(Image.new("RGBA", (32, 32), "orange"))
    stage.add(cat)
    cat.on_key_down(Key.RIGHT, Script(Sprite).glide_by(x=60, seconds=0.4))
    stage.run()


if __name__ == "__main__":
    main()
