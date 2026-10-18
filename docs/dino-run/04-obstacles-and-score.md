# 4. Add a challenge

[Home](../index.md) · [Dino Dash course](index.md)

**Goal:** run past obstacles and keep score.

Run [main.py](../../examples/dino_run/main.py). You now have the complete game!
Read the named functions below in that file; you do not need to type it all at once.

## Make a cactus appear

`spawn()` chooses a cactus or rock. Once the score reaches 200, it can choose birds.
`choice(kinds)` picks one item from a tuple.

The new Sprite uses `BodyType.KINEMATIC`: our code controls its speed and physics
can detect its contact with the dinosaur. `obstacles.append(obstacle)` adds it
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

## Move each obstacle

`update()` reads `event.data`, works out the speed, and sets each obstacle's
`body.velocity`. `for obstacle in obstacles.copy():` visits each one.
We visit a copy because we might remove an obstacle from the original list.
`stage.remove(obstacle)` also releases its physical body.

`dino.body.touching(obstacle.body)` checks physical contact. A bump ends the run.
Coin pickup uses `dino.touching(coin)`, a simpler picture-bounds overlap.

## Work out a score

`distance += speed * dt` remembers the journey. `score()` returns
`int(distance / 10) + coins * 25`. `int` gives us a whole number.
We calculate score from those facts instead of maintaining another counter.

`global distance` lets a function reassign a module-level name. Changing a Sprite's
property or calling `obstacles.append(...)` does not need `global`.

**Make it yours:** change `1.4` to `1.8` for more space between obstacles.
Restart before trying the new version.

[Next: finish the game →](05-finish-game.md)
