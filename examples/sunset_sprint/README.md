# 🏁 Sunset Sprint

Race three computer cars around the sunset track. You steer freely: stay on the
road, take corners, overtake, and be first to finish three laps.

```sh
plocks run examples/sunset_sprint
```

**WASD or arrows:** drive · **Space:** boost · **R:** restart

## What you'll learn

- **Speed and direction:** W/S change speed while A/D points your car.
- **Loops:** Each computer car moves in one `for` loop.
- **Tuples:** Every bot remembers its picture, progress, lane, speed and name.
- **Maths:** `sin` and `cos` place bots around the oval; your car moves freely.
- **`if`:** Grass slows you, walls bounce you, and a close car bumps you.

## Make it yours

1. Change Ruby's `0.185` speed to make the first rival faster.
2. Change `3` in `player_progress >= 3` to make a longer race.
3. Change the `330` top speed to see how a faster player feels.

The cars, track, music and sounds are original assets made for this example. Copy
the whole folder, including `assets/`, into your own project to change it.
