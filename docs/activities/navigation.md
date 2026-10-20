# Find a way around walls

[Home](../index.md)

**Goal:** let a character find and follow a route.

## 1. Try Maze Quest

```sh
plocks examples maze_quest --copy-to route-game
cd route-game
python main.py
```

Click a floor tile. Your hero walks around walls. Clicking a wall shows a message.

## 2. Read the route function

In `main.py`, find `choose_route`. Its important lines are:

```python
route = world.find_path(start=hero.position, goal=goal, actor=hero)
if route is None:
    hero.say("That way is blocked.", seconds=1)
else:
    hero.follow_path(route, speed=180)
```

`actor=hero` checks that the hero fits. The route is a tuple of world positions.
`None` means there is no route. Both solid and one-way tiles count as walls here.
This is for walking through top-down maps; it does not plan platform jumps.

## 3. Make it yours

Change `speed=180` to `speed=100`. Edit a `#` in the map into a `.` to open a door.
Save and run again. A new route sees your edited map; an old route stays unchanged.

You can also put `follow_path` inside `hero.sequence()` or `hero.repeat()`.
Individual actions still support `after=previous_action`.
Ask for a new route when the destination changes, rather than in every update.

**Stuck?** A large character may not fit a narrow passage. Try a smaller image.

[Next: collect a coin](touch.md)
