# 🪙 Coin Quest

A Mario-style adventure: collect nine coins and reach the flag. Watch the gap!

## Play

```sh
plocks run mario
```

To edit your own copy, run `plocks examples mario --copy-to my-game`.
Open that new folder and run `python main.py` there. Keep the `assets` folder.


**Arrows:** run · **Space:** jump · **R:** restart

## What you'll learn

- **Tilemaps:** `rows` builds the world: G is grass, D is dirt, S is stone, . is empty.
- **Lists:** Collected coins leave the `coins` list.
- **Conditions:** Land on an enemy to bounce; touch its side and the run ends.

Solid tiles stop you from the side, above and below. Read the short comments in `update`.

## Make it yours

1. Move a coin in `reset`.
2. Change a row of tiles to make a new ledge.
3. Change jump speed from 570 to 620.

**Your own project?** Copy this whole folder, keep `assets/` beside `main.py`,
and run `python main.py` with Plocks installed. From another folder, use
`python path/to/the/game/main.py` or `plocks run path/to/the/game`.
