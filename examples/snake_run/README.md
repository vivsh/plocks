# 🐍 Snake Run

Eat apples to grow, dodge rocks, and reach the finish!

## Play

```sh
plocks run examples/snake_run
```

**Arrows:** steer · **R:** restart

## What you'll learn

- **Lists:** `history` remembers the head's earlier positions.
- **Loops:** Each body piece follows a slightly older position.
- **Perspective:** Faraway objects look smaller and higher on the screen.

This is a 2D game that looks 3D. Rocks remove two body pieces; losing them all
ends the run. The snake grows to eleven pieces, including its head.

## Make it yours

1. Change the track speed from 110 to 90.
2. Change the lane sequence in `reset`.
3. Give the snake head PNG a new expression.

**Your own project?** Copy this whole folder, keep `assets/` beside `main.py`,
and run `python main.py` with Plocks installed. From another folder, use
`python path/to/the/game/main.py` or `plocks run path/to/the/game`.
