# 🌴 Jungle Run

A Contra-style mission: defeat six robots and reach the gold flag.

## Play

```sh
plocks run examples/jungle_run
```

**Arrows:** run · **Space:** jump · **Hold X:** shoot · **P:** pause · **R:** restart

## What you'll learn

- **Functions:** `fire` makes bullets; `hurt` changes health.
- **Lists and collisions:** Check each bullet, then remove it when it hits something.
- **Scripts:** Robots walk and fire at the same time.

Try this after Sky Steps. Jump through platforms from below and land on top.
This bigger game writes its own gravity and landing rules.

## Make it yours

1. Change running speed from 220 to 280.
2. Move a robot in `spawn_enemies`.
3. Replace `assets/hero.png` with your own 32 × 40 character.

**Your own project?** Copy this whole folder, keep `assets/` beside `main.py`,
and run `python main.py` with Plocks installed. From another folder, use
`python path/to/the/game/main.py` or `plocks run path/to/the/game`.
