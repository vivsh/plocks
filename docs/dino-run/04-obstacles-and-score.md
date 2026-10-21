# 4. Add a challenge

[Home](../index.md) · [Dino Dash course](index.md)

**Goal:** run past obstacles and keep score.

Run [main.py](../../src/plocks/_games/dino_run/main.py). You now have the complete game!
Read the named functions below in that file; you do not need to type it all at once.

## Make a cactus appear

`spawn()` chooses a cactus or rock. Once the score reaches 200, it can choose birds.
`choice(kinds)` picks one item from a tuple.

The new Sprite uses `BodyType.STATIC`: it stays at one place in the world.
The dinosaur runs towards it. Physics can detect their contact. `obstacles.append(obstacle)` adds it
to our list. A list holds several things and can grow or shrink.

## Repeat a job

```python
spawn_obstacle = Message[None]("spawn obstacle")
spawning = dino.repeat().wait(1.4).broadcast(spawn_obstacle)
```

The script waits, broadcasts, and repeats. The `@stage.on_broadcast(...)` handler
runs `spawn()`. `None` means this message carries no extra data.
`reset()` starts the script with `dino.act(spawning)`.

Messages are named tokens: use the **same token object** to send and receive.
Broadcasts arrive in a later delivery cycle, rather than calling a function recursively.

## Let the camera follow

`update()` sets the dinosaur's forward `body.velocity`, keeping its current
up-and-down velocity so jumps still work. `stage.follow(dino, offset=(260, 0), ... )`
keeps it near the left of the screen. The camera bounds keep the view level during jumps.

Obstacles appear just beyond `stage.world_bounds.right`. Their world positions
stay fixed: the camera makes them move across the screen. Coins stay fixed too.
`for obstacle in obstacles.copy():` visits each obstacle.
We visit a copy because we might remove an obstacle from the original list.
`stage.remove(obstacle)` also releases its physical body.

`dino.body.touching(obstacle.body)` checks physical contact. `hitbox(...)` also
checks the smaller collision boxes before physics separates them. This catches
standing up beneath a bird. A bump ends the run.
Coin pickup uses `dino.touching(coin)`, a simpler picture-bounds overlap.

## Work out a score

The dinosaur starts at x = -260, so `dino.x + 260` is how far it has run.
`score()` gives one point per ten pixels, plus 25 per coin. `int(...)` makes a
whole number. We calculate distance from the dinosaur instead of storing a timer.

`global coins` lets a function reassign the module-level coin count. Changing a
Sprite's property or calling `obstacles.append(...)` does not need `global`.

**Make it yours:** change `1.4` to `1.8` for more space between obstacles.
Restart before trying the new version.

[Next: finish the game →](05-finish-game.md)
