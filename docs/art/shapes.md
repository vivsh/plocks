# Make a shape 🔵

[Home](../index.md) · [Make artwork](index.md)

**Goal:** make a ball or block without drawing a picture first.
No image files or extra imports needed!

Save this as `main.py`, then run `python main.py`:

```python
from plocks import Event, Image, Sprite, Stage

stage = Stage(background="midnightblue")
ball = Sprite(Image.circle(20, color="gold"), x=-100)
platform = Sprite(Image.rectangle(140, 20, color="seagreen"), y=-80)
stage.add(ball)
stage.add(platform)


@ball.on_start
def roll(event: Event[Sprite, None]) -> None:
    # Give the ball a plan: glide right, then glide back. Keep repeating!
    trip = event.target.repeat()
    trip.glide_by(x=200, seconds=2)
    trip.glide_by(x=-200, seconds=2)
    event.target.act(trip)


def main() -> None:
    stage.run()


if __name__ == "__main__":
    main()
```

The ball glides; the platform stays still. Shapes are pictures, so they don't
fall or bounce by themselves. Turn on physics when you want that.

## Choose your shape

```python
block = Image.rectangle(80, 30, color="orange")
ball = Image.circle(20, color="gold")
oval = Image.ellipse(60, 30, color="skyblue")
arrow = Image.triangle(30, 40, color="tomato").rotated(90)
kite = Image.polygon(((20, 0), (40, 20), (20, 50), (0, 20)), color="violet")
```

Sizes are whole pixels greater than zero. A circle's **radius** is half its
width: `circle(20)` is 40 pixels wide. Triangles point up until you rotate them.

Polygon points go right and down, like points on a picture. The result is cropped
around them, including the last pixel. The kite above is 41 × 51 pixels.
Use at least three points and keep its edges from crossing.

## Add an outline

```python
ring = Image.circle(20, color=None, outline="white", outline_width=3)
coin = Image.circle(16, color="gold", outline="orange", outline_width=2)
```

`color=None` leaves the inside see-through. Outlines stay inside the shape.
The default fill is white; the default outline width is one pixel.
For see-through colors, try `color=(255, 0, 0, 128)`—red at half opacity.

## Choose where it stands

```python
from plocks import Anchor

spike = Image.triangle(32, 40, color="red", anchor=Anchor.BOTTOM_CENTER)
```

Now a sprite's position is at the spike's feet. The usual default is `CENTER`.
Shapes work with [image transforms and anchors](images.md), tile palettes and
Puppet parts, just like file images.

**Try it:** change the ball into a triangle. Can you make a hollow triangle?
