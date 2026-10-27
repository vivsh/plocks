# Pictures, grids and names

[Home](../index.md) · [Make artwork](index.md)

**Goal:** pick pictures and choose where your character stands.

## 1. Put its feet in the right place

```python
from plocks import Anchor, Image, Sprite

hero = Sprite(Image("assets/hero.png", anchor=Anchor.BOTTOM_CENTER))
```

The hero's position is now at its feet. `Anchor.CENTER` is the default.
Try `TOP_LEFT`, `TOP_CENTER` or `BOTTOM_RIGHT` too. Exact points still work:
`anchor=(8, 4)` measures right and down from the picture's top-left.

Images stay unchanged when you make a new version:

```python
left = hero.image.flipped(horizontal=True)
small = hero.image.resized(16, 24)
hero.image = left
```

### Remove extra space

```python
picture = Image("assets/hero.png").trimmed()
picture = Image("assets/hero-on-white.png").trimmed(color="white")
```

`trimmed()` cuts away transparent padding around the outside. Choose a color to
also cut away matching border pixels. Names, RGB and RGBA tuples work; the match
is exact. It keeps inside pixels, including holes and shadows, unchanged.
The original picture stays unchanged too.

The anchor moves with the crop, so your artwork stays in place. To put the feet
at the bottom of the newly cropped picture, use:

```python
picture = picture.with_anchor(Anchor.BOTTOM_CENTER)
```

If nothing needs cutting, or the whole picture is empty/background, you get the
same image back. Trimming does not turn an interior white background transparent.

## 2. Pick from a grid

Use `ImageGrid` when every frame has the same size:

```python
from plocks import ImageGrid

walk = ImageGrid("assets/hero.png", frame_size=(32, 40))
frames = walk.frames(row=0, anchor=Anchor.BOTTOM_CENTER)
hero.on_start(hero.repeat().images(frames, fps=8))
```

Rows and columns start at zero. `walk.frame(row=0, column=1)` picks one picture.
Pixelorama exports with timing still use `PixeloramaSheet`.

## 3. Pick pictures by name

`ImageMap` uses a JSON file to find pictures with different sizes. Try our tiny
ready-made map first:

```sh
plocks examples asset_workshop --copy-to picture-game
cd picture-game
```

Replace `main.py` with:

```python
from pathlib import Path
from plocks import Anchor, ImageMap, Sprite, Stage

assets = Path(__file__).resolve().parent / "assets"
stage = Stage(background="skyblue")

# The JSON names two different-sized pieces of our tile picture.
pictures = ImageMap(assets / "ground.png", metadata=assets / "pictures.json")
big = Sprite(pictures["big_tile"].with_anchor(Anchor.BOTTOM_CENTER), x=-50)
small = Sprite(pictures["small_tile"].with_anchor(Anchor.BOTTOM_CENTER), x=50)
stage.add(big)
stage.add(small)

if __name__ == "__main__":
    stage.run()
```

Run `python main.py`. Both pictures stand on the same y position!
Open `assets/pictures.json` and find their names and rectangle sizes.

For your own packed pictures, export **JSON Hash**, at 100% size, with trimming
and rotation switched off. If the files share a name, such as `actors.png` and
`actors.json`, simply write `ImageMap(assets / "actors.png")`.
Names match the JSON exactly, including `.png` if it appears there.

**Your own format?** Give `metadata` an ordinary typed function:

```python
from plocks import Image


def load_pictures(atlas: Image) -> dict[str, Image]:
    # Read your own data here, then return the named pictures.
    return {"tile": atlas.cropped(0, 0, 16, 16).with_anchor(Anchor.CENTER)}


pictures = ImageMap(assets / "ground.png", metadata=load_pictures)
```

The function runs once. It can read JSON, CSV or another format you choose.
Use `hero.set_image(picture, after=walking)` to change a picture after an action.
Use `hero.images(frames, fps=8)` to play a flipbook.

Older code using `Costume`, `SpriteSheet`, `costume` or `costumes` still works,
but gives a deprecation notice. Use `Image`, `ImageGrid`, `image` and `images` now.
