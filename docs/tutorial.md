# Make things happen

Start with the complete game in the [README](../README.md), then choose a game from
the [eight-example collection](../examples/README.md). These snippets belong
at module level, after adding your actors to the stage. Keep the final
`stage.run()` inside an `if __name__ == "__main__":` guard.

## Move, then move again

```python
first = hero.glide_by(x=100, seconds=1)
hero.glide_by(y=50, seconds=0.5, after=first)
```

Each call returns an `Action`. The second action starts after the first succeeds.
Without `after`, both can move at once because they control different coordinates.
The starting position is captured when movement begins.

## Repeat a recipe

```python
patrol = hero.repeat(10)
patrol.glide_by(x=100, seconds=1)
patrol.wait(0.2)
patrol.glide_by(x=-100, seconds=1)
hero.on_start(patrol)
```

Omit `10` to repeat until stopped. Recording the recipe does not move the actor.
`hero.act(patrol)` starts a fresh snapshot; editing the recipe later affects future runs.
A recipe belongs to one actor. Use a function accepting an actor to make similar recipes
for two actors.

## Jump on a key press

```python
from plocks import Action, Ease, Key


@hero.on_key_down(Key.SPACE)
def jump() -> Action:
    up = hero.glide_by(y=100, seconds=0.3, easing=Ease.OUT)
    return hero.glide_by(y=-100, seconds=0.3, easing=Ease.IN, after=up)
```

Returning the last Action keeps the handler busy. Repeated Space presses are ignored
until it finishes, so the jump needs no flag or timer. This is an authored motion;
use [physics](physics.md) for a character that falls onto platforms.

## Walk and change costumes

```python
walking = hero.repeat().costumes(sheet.frames(row=1), fps=10)
travel = hero.sequence().glide_to(x=180, seconds=2)
arrival = hero.during(travel, meanwhile=walking)
hero.set_costume(idle, after=arrival)
```

The costume loop stops when travel finishes. Every costume, including the last,
lasts `1 / fps` seconds.

## Decide while the game runs

```python
from plocks import Action, Key


def choose() -> Action:
    if stage.keyboard.is_down(Key.RIGHT):
        return hero.move(2)
    return hero.wait(0)


hero.act(hero.repeat().call(choose))
```

`call` runs an ordinary function when the recipe reaches it. A Python `if` written
outside a function runs while you are building the game, not repeatedly during play.

## Send a message

```python
from plocks import Action, Key, Message

points = Message[int]("points")
score = 0


@friend.on_message(points)
def add_points(amount: int) -> None:
    global score
    score += amount
    friend.say(f"Score: {score}", seconds=1)


@hero.on_key_down(Key.H)
def collect() -> Action:
    return stage.broadcast(points, 10)
```

The receiver returns `None`, so later messages can update the score immediately.
If it returned the speech Action, it would stay busy until the speech ended.
A `Signal("go")` carries no data. Messages are matched by token identity, not name.

## Make a Puppet wave

```python
from plocks import HumanJoint, Puppet

person = Puppet.stick_figure()
stage.add(person)
rest = person.pose
raised = rest.with_angles({HumanJoint.RIGHT_ELBOW: 60})
person.act(person.repeat().poses((rest, raised, rest), fps=2))
```

For a custom Puppet, attach PNG files to joint pivots. Each part's costume anchor
sits on its pivot; parent rotations move child pivots. Poses must belong to that exact skeleton.

## Advanced: await the same actions

```python
@hero.on_key_down(Key.A)
async def jump_again() -> None:
    await hero.glide_by(y=100, seconds=0.3)
    await hero.glide_by(y=-100, seconds=0.3)
```

The method calls are the same. Await observes the scheduled action; it does not start
a second copy. Plocks coroutines await Plocks actions, not asyncio tasks, sleeps, or network I/O.
