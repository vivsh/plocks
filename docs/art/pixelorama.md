# 🐾 Make a character wiggle

[Home](../index.md) · [Make artwork](index.md)

Turn your drawings into a little flipbook on screen.
A **frame** is one picture in that flipbook.

**Ready?** Use the `my-game` copy from [Get ready](index.md#get-ready).
You can try the code with its pictures before drawing your own.

## 1. Draw two pictures

In Pixelorama, make a new **32 × 40** picture. Draw a funny face or tiny person.
Add another frame in the timeline at the bottom. Change something: close an eye,
move a foot, or raise a hand. Press Play to watch your pictures take turns.

Save your drawing as `hero.pxo` so you can edit it again later.

## 2. Make the game files

Choose **File → Export** (or **Export As** to choose a new folder).
Pick **Spritesheet**: all your frames in one picture.
Ask a grown-up to help set these options once:

| Setting | Choose |
| --- | --- |
| Picture and extra data | PNG, with JSON export switched on |
| Frames and layout | All frames, Rows, one row |
| Playback and layers | Forward, merged visible layers, no extra repetitions |
| Size and trimming | 100%, no cropping, split layers off |

Export into `my-game/assets` as **`hero.png` and `hero.json`**.
The PNG holds the pictures. The JSON tells Plocks their size and timing.
Keep both files together. Export both again whenever you change the drawing.

## 3. Try this Python

Replace your copy's `main.py` with:

```python
from pathlib import Path
from plocks import PixeloramaSheet, Sprite, Stage

assets = Path(__file__).resolve().parent / "assets"
stage = Stage(background="skyblue")

# Read our pictures, then show the first one.
art = PixeloramaSheet(assets / "hero.png")
hero = Sprite(art.frames[0])
hero.scale = 3
stage.add(hero)

# Take turns showing every picture. Keep going!
hero.on_start(art.animation().repeat())

if __name__ == "__main__":
    stage.run()
```

## 4. Play!

Open a terminal in `my-game` and run `python main.py`.
Your pictures should keep taking turns on the blue stage.
Close the game before exporting new pictures, then run it again.

**Make it yours:** add a third frame with a silly hat!

**Stuck?** Check that `hero.png` and `hero.json` have matching names and live
in `assets`. If nothing seems to move, make the frames look different.
