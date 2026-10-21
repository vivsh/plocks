# Let the camera follow

[Home](../index.md)

**Goal:** follow your character through a world bigger than the window.

Your world has places, like a map. `hero.x` and a tile map's `x` are places in
that world. The camera chooses which part you see. Moving it makes pictures and
tiles scroll on screen; you do not need to move the world yourself.

Physics is a separate choice. `Stage()` keeps it off; `Stage(physics=True)` turns
on gravity and physical collisions. Camera following works with either.

## 1. Copy a game

```sh
plocks examples maze_quest --copy-to camera-game
cd camera-game
```

## 2. Find the follow line

Open `main.py`. This line follows the hero and keeps the view inside the maze:

```python
stage.follow(hero, bounds=world.bounds, smoothing=0.12)
```

Change `0.12` to `0.3` for a gentler camera. Use `0` for immediate following.
Run `python main.py`, then click a distant floor tile.

## 3. Take control

For a fixed view, replace the follow line with:

```python
stage.camera = (0, 0)
```

Setting the camera yourself stops following. `stage.stop_following()` instead
leaves the view exactly where it is. Pausing freezes automatic following too.

**Notice:** Canvas text, labels and buttons stay on the screen while the maze moves.

## Try other views

- **Beat Blocks:** the cube runs through fixed spikes; `offset=(120, 0)` leaves
  space ahead. One-window-high bounds keep the camera level during jumps.
- **Dino Dash:** floor sections are added ahead and removed behind. Existing
  sections stay at their world positions.
- **Fruit Slice:** the camera stays at `(0, 0)` so mouse swipes line up with fruit.
- **Temple Trail and Snake Run:** perspective code shrinks faraway pictures to
  look 3D. Their 2D camera stays fixed.

Tile maps can use `parallax=(0.3, 1)` to make distant scenery scroll more slowly.
Solid tiles use the normal `(1, 1)` so their pictures match their physical ground.

Mouse events give screen positions. In a scrolling world, add `stage.camera` to
find the world position, as Scrolling World's painting handler does.

[Next: screen controls](ui.md)
