# Collect a coin once

[Home](../index.md)

**Goal:** make something happen when two characters meet.

## 1. Play

```sh
plocks run maze_quest
```

Click floor tiles to collect coins. A coin adds one point, even if you stay there.

## 2. Make your own copy

```sh
plocks examples maze_quest --copy-to my-maze
cd my-maze
```

Open `main.py`. Find the `collect` function and add this line inside it:

```python
hero.say("Yay!", seconds=0.5)
```

## 3. Try a new reaction

Run `python main.py`. Collect a coin and watch your hero speak!
The example connects each coin with:

```python
hero.on_touch(coin)(collect)
```

`event.target` is the hero; `event.data` is that coin. `on_touch` runs when overlap
starts. `on_touch_end` runs when it ends. Removing a coin does not call its end event.
Pictures are checked using their rectangular bounds.

**Try this:** change the words. Then find `hurt` and change the damage from 25 to 10.

[Next: find a route](navigation.md)
