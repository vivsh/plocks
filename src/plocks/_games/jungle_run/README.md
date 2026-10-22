# 🌴 Jungle Run

A Contra-style mission: defeat six robots and reach the gold flag.

## Play

```sh
plocks run jungle_run
```

To edit your own copy, run `plocks examples jungle_run --copy-to my-game`.
Open that new folder and run `python main.py` there. Keep the `assets` folder.


**Arrows:** run · **Space:** jump · **Hold X:** shoot · **P:** pause · **R:** restart

## What you'll learn

- **Functions:** `fire` makes bullets; `hurt` changes health.
- **Lists and collisions:** Check each bullet, then remove it when it hits something.
- **Scripts:** Robots walk and fire at the same time.
- **Physics:** Gravity and one-way platforms handle jumps and landings.
- **Turbo input:** `repeat=0.16` keeps shooting while X is held.

Try this after Sky Steps. Jump through platforms from below and land on top.
Plocks handles gravity, landing and camera scrolling. This bigger game still
checks the path of each bullet so fast shots cannot skip a robot.

## Make it yours

1. Change running speed from 220 to 280.
2. Move a robot in `spawn_enemies`.
3. Replace `assets/hero.png` with your own 32 × 40 character.

**Your own project?** Copy this whole folder, keep `assets/` beside `main.py`,
and run `python main.py` with Plocks installed. From another folder, use
`python path/to/the/game/main.py` or `plocks run path/to/the/game`.

## Screen controls

The green health bar shrinks when you get hit. A pause Panel has Continue or Play again; P and R still work.
