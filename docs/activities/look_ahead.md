# Let an enemy look ahead

[Home](../index.md) · [More activities](index.md)

Save [this small game](look_ahead.py) and run `python look_ahead.py`.
Walk with the arrow keys. The blue enemy turns when its next step is blocked.
The gold line shows where it looks for your orange character.

## Can I go there?

```python
if enemy.body.can_travel(distance=10):
    enemy.body.travel_along(speed=80)
```

The check sweeps the enemy's whole collision shape along its facing direction.
It finds even thin obstacles between the start and destination. It changes nothing.
Give `direction=270` to check left, regardless of facing or current velocity.

Distances are world pixels. Speeds are pixels per second. Directions are clockwise:
0 up, 90 right, 180 down, 270 left. For a next-tick check, use `distance=speed * dt`.
This checks straight movement; it does not predict gravity or guarantee ground ahead.

## What is in the way?

```python
hit = enemy.body.shape_cast(distance=100)
if hit is not None:
    print(hit.target, hit.distance)
```

A hit tells you its `target`, world `point`, outward surface `normal`, and distance
travelled by your actor's anchor. For a tile, `hit.cell` contains `(row, column)`;
for another actor it is `None`. Results are snapshots, even after a tile is edited.

To sweep your own shape, import `Box` and call:

```python
hit = stage.physics.shape_cast(Box(20, 30), start=(0, 0), end=(100, 0))
```

Here `direction` rotates the box and `scale` changes its size. The movement follows
`start` to `end`; the cast does not rotate the shape during the journey.

## Can I see the hero?

```python
hit = stage.physics.raycast(enemy.position, hero.position, ignore=(enemy,))
if hit is not None and hit.target is hero:
    print("I see you!")
```

A ray is a thin line. It returns the first hit, or `None` for no hit. Rays can start
inside an object: that is a zero-distance hit, so ignore the starting actor yourself.
Body casts already ignore their own actor. Sensors are skipped by all these queries.

## Skip a friend

```python
enemy.body.can_travel(distance=10, ignore=(friend,))
```

For a rule, use a typed ordinary function:

```python
from plocks import CastTarget

def ignore_friend(target: CastTarget) -> bool:
    return target is friend

enemy.body.can_travel(distance=10, ignore=ignore_friend)
```

Return `True` to skip the object. A whole TileMap can be skipped too. Functions
must not change the game during a query. Ignore affects the check only: it does
not make real collisions pass through friends.

Only physics-enabled actors and solid/one-way tile cells are queried. Hidden bodies
still count. One-way tiles block downward movement from above; rays see their top
surface from either side. Edge contact allows sliding or moving away. Existing tiny
resting contact penetration is tolerated while separating/sliding; a deep starting
overlap is a zero-distance hit. Exact ties use stage insertion order, then tile order.

For platformer walking, keep vertical velocity instead of replacing it with
`travel_along()`, which sets both velocity components. Queries require an open
physics world; saved body handles stop working after removal.
