# Jungle Run

A short original run-and-gun level inspired by classic arcade action games.
Run through a jungle outpost, defeat six sentry robots, and reach the gold flag.

With Plocks installed in your active virtual environment, copy `main.py` into
your project and run:

```sh
python main.py
```

From a Plocks checkout, use `plocks run examples/jungle_run`.
All artwork is generated with Pillow; no downloaded assets are required.

| Control | Action |
| --- | --- |
| Left / Right arrows | Run and face left / right |
| Space | Jump; you can move and shoot in the air |
| Hold X | Fire continuously in the direction you face |
| P | Pause or resume |
| R | Restart the level |

Platforms are one-way: jump through them from below and land on top. You have
three health points, with a short grace period after taking damage. Jump to shoot
robots on raised platforms, and jump over incoming fire.

This is an intermediate example. It combines block-based walking animation,
structured patrol/fire behaviors, scrolling tile scenery, and a synchronous
update callback for authored gravity, landing and projectile collisions. Those
platforming rules belong to this game; Plocks does not apply automatic physics.
