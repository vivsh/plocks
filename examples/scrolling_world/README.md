# 🖌️ Scrolling World

Explore a wide world, then paint your own paths.

## Play

```sh
plocks run examples/scrolling_world
```

**Arrows:** explore · **1 / 2 / 3:** choose grass / dirt / stone

**Left click:** paint · **Right click:** erase

## What you'll learn

- **Tilemaps and layers:** A grid builds the ground; another puts plants in front.
- **Camera:** The window follows the explorer through a bigger world.
- **Parallax:** Distant clouds move less than nearby hills, making the world feel deep.

The explorer is a guide for painting. There is no falling or tile collision in this game.

## Make it yours

1. Change the mountains' movement factor from 0.3 to 0.5.
2. Set `leaves.layer` to -1 to put plants behind the explorer.
3. Edit `rows` to build a new landscape.

**Your own project?** Copy this whole folder, keep `assets/` beside `main.py`,
and run `python main.py` with Plocks installed. It also works from another folder
using `python path/to/the/game/main.py`.
