# 🖌️ Scrolling World

Explore a wide world, then paint your own paths.

## Play

```sh
plocks run scrolling_world
```

To edit your own copy, run `plocks examples scrolling_world --copy-to my-game`.
Open that new folder and run `python main.py` there. Keep the `assets` folder.


**Arrows:** explore · **1 / 2 / 3:** choose grass / dirt / stone

**Left click:** paint · **Right click:** erase

## What you'll learn

- **Tilemaps and layers:** A grid builds the ground; another puts plants in front.
- **Camera:** `stage.follow` follows the explorer and stops at the world's edges.
- **Parallax:** Each background tile map has a scrolling factor. Clouds move
  less than nearby hills; Plocks does the scrolling for us.

The explorer is a guide for painting. There is no falling or tile collision in this game.

## Make it yours

1. Change the mountains' movement factor from 0.3 to 0.5.
2. Set `leaves.layer` to -1 to put plants behind the explorer.
3. Edit `rows` to build a new landscape.

**Your own project?** Copy this whole folder, keep `assets/` beside `main.py`,
and run `python main.py` with Plocks installed. From another folder, use
`python path/to/the/game/main.py` or `plocks run path/to/the/game`.
