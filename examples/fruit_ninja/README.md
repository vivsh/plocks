# 🍉 Fruit Slice

A Fruit Ninja-style game: swipe fruit, avoid bombs. Three missed fruit end the round.

## Play

```sh
plocks run examples/fruit_ninja
```

**Hold the left mouse button and move:** slice · **R:** restart

## What you'll learn

- **Randomness:** Each toss chooses a fruit, position and speed.
- **Mouse input:** Remember the last mouse position to follow the whole swipe.
- **Geometry:** `crosses` checks whether a swipe passes through a fruit.

The maths in `crosses` is a stretch challenge. You can use its yes/no answer first.
Cutting several fruit in one step earns a bonus. Use a mouse, not a touchscreen.

## Make it yours

1. Change the throw interval from 0.8 to 1.2 seconds.
2. Allow five misses instead of three; update the score text too.
3. Paint a fruit and its two half pictures in `assets/`.

**Your own project?** Copy this whole folder, keep `assets/` beside `main.py`,
and run `python main.py` with Plocks installed. From another folder, use
`python path/to/the/game/main.py` or `plocks run path/to/the/game`.
