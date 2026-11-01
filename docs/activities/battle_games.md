# Drive, jump and blast!

[Home](../index.md) · [More activities](index.md)

Try [this tiny tank game](battle_games.py): save it and run `python battle_games.py`.
Use the arrows to drive and Space to blast a brick. It uses Plocks' shape images,
so you don't need to download artwork.

## Drive one tile

```python
tank.position = world.cell_center(row=5, column=2)
tank.move_cell(world, direction=90, seconds=0.2)
```

Start at a cell center. Directions are **0 up, 90 right, 180 down, 270 left**.
A wall or map edge stops a step from starting. Another step requested while driving
is ignored. The tank needs `BodyType.KINEMATIC`, or no physical body.

Changing the map can stop a step partway. Canceling also leaves it where it stopped.
To start another cell step, first put it at a cell center. This helper doesn't turn
the tank: set `tank.direction` when you want its picture to turn.

## Run and jump

For a Contra-style hero on a stage with gravity:

```python
hero.body.walk(speed=150)  # Right. Negative goes left; zero stops sideways motion.
hero.body.jump(height=90)  # Jump if standing on something.
```

Walking keeps the up/down speed. Jump height is in pixels under normal gravity;
it works out the push for you. Airborne jumps return `False`. Drag, moving platforms
and other pushes can change the height reached. Try these in **Clone Blaster**:

```sh
plocks run clone_blaster
```

## Make friendly shots

```python
hero.body.collision_group = "player"
bullet.body.collision_group = "player-shot"
bullet.body.collides_with = {"enemy", "terrain"}
```

Put enemy bodies in group `"enemy"`. Tiles use `"terrain"` already. Both bodies
must allow each other's group. The default accepts every group; an empty set
accepts none. Copies inherit these settings.

Filters affect physics, body casts and bullet hits. Picture-overlap tests such as
`touching()` and `on_touch()` keep their usual rules.

## Catch fast bullets

After adding a kinematic bullet:

```python
bullet.body.projectile = True
```

It flies as a sensor, stops at its first blocking hit, and calls `on_hit`. Even thin walls
between frames are checked. You choose what happens next:

```python
@bullet.on_hit
def hit(event: Event[Sprite, Collision]) -> None:
    print(event.data.target)
    event.target.remove()
```

Import `Event`, `Sprite` and `Collision` from `plocks`. Hit data also has `point`,
`normal` and tile `cell`. Normal `on_touch` watches picture overlap;
use [on_hit](hits.md) for physical contacts, including projectile impacts. Projectile mode needs straight, nonrotating
kinematic bodies without physical connections. Turning between flights is fine.
Turning projectile mode off leaves its sensor setting on.

Missed bullets can tidy themselves up: `copy.remove_after(seconds=2)`.
Pause freezes that wait. To cancel a planned removal, save the returned Action
and call its `cancel()` method.

## Give enemies eyes and a timer

```python
if enemy.can_see(hero, distance=300):
    print("Spotted you!")
```

Walls block sight. Both actors need to be on the same physics stage. This checks
between their positions; it doesn't turn or move the enemy.

```python
@stage.every(seconds=3)
def spawn(event: Event[Stage, float]) -> None:
    if enemy.clone_count < 4:
        copy = enemy.clone()
        copy.position = (100, 50)
```

The first call happens after three game seconds. Pause freezes the timer.
`event.data` is the interval you chose. Keep the hidden enemy original attached,
just like the bullet original in the tank game.

**Make it yours:** add a red target, change the driving speed, or make steel tiles
that bullets cannot destroy.
