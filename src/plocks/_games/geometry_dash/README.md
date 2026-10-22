# 🟨 Beat Blocks

A Geometry Dash-style challenge: jump over the pink spikes!

## Play

```sh
plocks run geometry_dash
```

To edit your own copy, run `plocks examples geometry_dash --copy-to my-game`.
Open that new folder and run `python main.py` there. Keep the `assets` folder.


**Space:** jump · **R:** restart

## What you'll learn

- **Actions:** Two glides joined with `after` make a jump—no jump timer needed.
- **Shapes:** `Image.rectangle` makes the cube; `Image.triangle` makes the spikes.
- **Lists and loops:** The spike positions make your course.
- **Hitboxes:** Invisible boxes check whether two things crash.
- **Camera:** `stage.follow(...)` follows the cube; the floor and spikes stay put.

The cube runs by itself. Physics is off: glides give the jump its chosen path.
The camera stays level during jumps and follows again after restarting.
Jump timing is the challenge; there is no music timing.

## Make it yours

1. Change running speed from 230 to 200.
2. Move a spike in the setup loop.
3. Change the cube's color, or use `Image(assets / "cube.png")` for its picture.

**Your own project?** Copy this whole folder, keep `assets/` beside `main.py`,
and run `python main.py` with Plocks installed. From another folder, use
`python path/to/the/game/main.py` or `plocks run path/to/the/game`.

## Screen controls

The progress bar fills as you run. After a crash or the finish, click Play again—or press R.
