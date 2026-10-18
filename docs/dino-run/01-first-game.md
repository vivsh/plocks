# 1. Meet your dinosaur

[Home](../index.md) · [Dino Dash course](index.md)

**Goal:** open a window with your dinosaur in a desert.

1. Open [01_hello.py](../../examples/dino_run/01_hello.py).
2. Run `python 01_hello.py` inside your downloaded `dino_run` folder.
3. Change `x=-260` to `x=100`. Close the game and run it again.

## Read the small pieces

```python
from plocks import Sprite, Stage
```

`import` brings tools into our program. A **Stage** is the game window.
A **Sprite** is a character with a picture, called a costume.

```python
stage = Stage(width=800, height=450, background="#fff0cc")
```

`stage` is a name for our window. `=` gives a name a value. The numbers set its
size in pixels; the string in quotes chooses a colour.

In the checkpoint, `Costume(...).resized(width=72, height=72)` makes a smaller
costume. It leaves the downloaded picture unchanged. `stage.add(dino)` puts
our character into the game.

`assets = Path(__file__).resolve().parent / "assets"` finds pictures beside this
Python file. Keep the `assets` folder when copying the game.
`BodyType.NONE` means decoration, with no physical body.

```python
if __name__ == "__main__":
    stage.run()
```

Keep this at the bottom. It starts the game when you run the file. The indented
line belongs to the `if`; use four spaces. Plocks handles drawing and the game loop.

**Make it yours:** change the window's background or dinosaur size.
Hover over `Stage`, `Sprite`, or `Costume` in your editor for help.

[Next: take control →](02-controls.md)
