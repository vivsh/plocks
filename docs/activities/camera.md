# Let the camera follow

[Home](../index.md)

**Goal:** follow your character through a world bigger than the window.

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

**Notice:** the score and buttons stay on the screen while the maze moves.

[Next: screen controls](ui.md)
