# Find the edges!

[Home](../index.md) · [More activities](index.md)

**Goal:** tell which sides your character reaches, including corners.

1. [Download Dino Dash](../dino-run/assets.md) and unzip it.
2. Save [this program](edges.py) as `edges.py` inside its `dino_run` folder.
3. Run `python edges.py`. Move with **arrows**; press **Space** to return home.

Reach the yellow rectangle first, then the screen edges. Try a corner!

## React to an edge

```python
from plocks import Edge, Event, Sprite

@hero.on_edge()
def reached(event: Event[Sprite, frozenset[Edge]]) -> None:
    if Edge.LEFT in event.data:
        event.target.say("Left edge!", seconds=1)
    if Edge.TOP in event.data:
        event.target.say("Top edge!", seconds=1)
```

Add the actor to its stage before registering. `event.target` is the character;
`event.source` is its stage. `event.data` is a read-only collection of **all** sides
currently reached: `Edge.LEFT`, `RIGHT`, `TOP` or `BOTTOM`. A top-left corner has two.
Puppets use the same API, with `Event[Puppet, frozenset[Edge]]` in the type hint.

Staying against an edge doesn't keep calling the function. Moving away and returning
triggers it again. Reaching another side also triggers it; leaving a side alone doesn't.

## Choose a rectangle

Omit bounds to watch the current viewport. It follows the camera, so camera movement
can trigger an event too. To watch a fixed area instead:

```python
from plocks import Bounds

arena = Bounds(left=-140, bottom=-90, right=140, top=90)

@hero.on_edge(arena)
def reached_arena(event: Event[Sprite, frozenset[Edge]]) -> None:
    print(event.data)
```

For a whole level, use `hero.on_edge(world.bounds)`, where `world` is your TileMap.
That captures its rectangle now; moving the map later doesn't move the watched area.
When a camera follows your hero near the screen center, level bounds can be more
useful than screen edges. [Learn about the camera](camera.md).

## Ask a question right now

```python
if hero.touching_edge():
    print("At or past a screen edge")

if hero.touching_edge(arena):
    print("At or past the arena boundary")
```

These queries return `True` or `False` immediately. The default needs an attached
actor; an explicit `Bounds` also works before adding it.

## Which sides does one point reach?

`contains()` answers **inside or outside**. `edges_at()` tells you the sides:

```python
arena = Bounds(left=-100, bottom=-50, right=100, top=50)
sides = arena.edges_at((120, 70))

if Edge.RIGHT in sides:
    print("At or past the right side")
if Edge.TOP in sides:
    print("At or past the top side")
```

A strictly inside point returns an empty `frozenset`. An edge point reports one
side; a corner can report two. Outside points report the sides they have crossed.
A point exactly on the boundary can satisfy `contains()` **and** report an edge.

Use `world.bounds.edges_at((x, y))` for a TileMap or
`stage.world_bounds.edges_at((x, y))` for the current viewport.
`arena.edges_at(hero.position)` checks only the hero's anchor point. Keep using
`hero.touching_edge(arena)` or `on_edge(arena)` for the whole character.

You can bind a script too:

```python
hero.on_edge(script=hero.sequence().say("Screen edge!", seconds=1))
hero.on_edge(arena, hero.sequence().say("Arena edge!", seconds=1))
```

**Remember:** edges notice the whole picture's bounding rectangle, including padding
and rotation. They count reaching **or crossing** a side, even if the actor is already
outside. Hidden actors still count. Detection doesn't clamp, bounce or create a
physical wall. Pause freezes edge events; queries still work. A trip outside and
back between game steps may be missed.

**Make it yours:** play a sound at the bottom edge, or make the dinosaur flash when
it reaches a corner!
