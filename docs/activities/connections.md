# Swing, cut and bounce

[Home](../index.md)

**Goal:** connect a ball to a fixed point with a physical rope.

## 1. Play Swing Lab

```sh
plocks examples swing_lab --copy-to my-swing
cd my-swing
python main.py
```

Press Space or click Cut rope. Press R to try again.

## 2. Change the rope

In `main.py`, find:

```python
rope = stage.physics.rope((0, 100), ball, length=150)
```

The point is the fixed end. `ball` is the moving end. Length is in pixels.
Try a longer rope. A rope can go slack; it only stops the ends getting too far apart.
The factory already connects it. Do not call `stage.add(rope)`.

To release it, the game calls:

```python
rope.disconnect()
```

Removing the ball also disconnects its rope. Pausing freezes the physics.
The drawing function uses `canvas.connection(rope)` to show the live link.

## 3. Try a spring

Run `plocks run robot_workshop`. Find the spring in its `main.py`.
A spring pulls and pushes toward `rest_length`. Try changing `stiffness=60` to 90.
`damping` helps its bouncing settle down. Keep changes small.

**Try this:** after `stage.add(ball)` in Swing Lab, add `ball.body.sensor = True`.
After you cut the rope, the ghost ball passes through the floor! Gravity still works.

[Next: build moving parts](assemblies.md)
