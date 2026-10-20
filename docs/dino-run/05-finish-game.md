# 5. Finish the game 🏁

[Home](../index.md) · [Dino Dash course](index.md)

**Goal:** make a game you want to play again.

Use the [complete project download](../downloads/dino-dash.zip), or
[read main.py](../../src/plocks/_games/dino_run/main.py).

| Control | Action |
| --- | --- |
| Space / Up / controller A / left click | Jump |
| Down / S / F / controller B | Duck while held |
| P | Pause or continue |
| R | Restart |

1. Clear the cacti and rocks. Collect a coin worth 25 points.
2. Reach 200 points. Duck under a bird!
3. Bump into something, press R, and try to beat your best score.

## Little finishing touches

**Ducking:** `wants_duck` reads held input. We replace the image and collision
box together, keeping the feet anchor in place. Changing an image alone does
not resize its physical collider.

**Coins:** the pickup list remembers coins still on screen. Touching one removes
it, adds to `coins`, and calls `stage.play(pop, volume=0.25)`. The sound is a
portable OGG file. One Sound can play several separate times.

**Words:** `@stage.on_draw` receives a `Canvas`. `canvas.text(...)` draws the score
on top of the world. An f-string, such as `f"Coins {coins}"`, inserts the current
number whenever that drawing function runs.

**Pause:** `stage.pause()` freezes simulation, physics, and scripts. Key callbacks
still run, so P can resume. Changing applications also suspends play automatically.

**Restart:** `reset()` stops the old spawn script, removes old obstacles and coins,
resets the dinosaur, then starts one new script. This prevents extra spawn loops.
The best score lasts until the window closes; this lesson does not save a file.

## Your next challenge

Change one rule: more coin points, a gentler speed increase, or earlier birds.
Then show someone what you made. Sound and downloaded files require the full
`assets` folder. Keep the other checkpoint scripts too if you want to revisit a step.

[Next: explore more Plocks →](06-more-plocks.md)
