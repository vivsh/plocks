# Build a moving machine

[Home](../index.md)

**Goal:** join separate parts into a robot arm or a wheeled cart.

## 1. Play Robot Workshop

```sh
plocks examples robot_workshop --copy-to my-workshop
cd my-workshop
python main.py
```

Arrows drive the cart. Hold Space/X to turn the arm. R makes another cart.
Click Drop chain to release the hanging beams.

## 2. Find a hinge

In `build_arm`, two picture centres are joined using local anchor points:

```python
elbow = stage.physics.hinge(
    upper, lower,
    anchor_a=(0, -30),
    anchor_b=(0, 30),
    limits=(-110, 110),
)
```

A hinge holds the two points together while the parts turn. Anchors are measured
from each actor's position: right is positive x, up is positive y. Set up the parts
so the anchors meet. Limits are degrees from their starting relative angle.

## 3. Drive it

A motor turns a hinge:

```python
drive = shoulder.motor(speed=0, max_torque=90000)
```

Find `controls` and change the arm's speed from 45 to 60. Positive speed turns
clockwise. Zero brakes the turning; `drive.disconnect()` lets it turn freely.

Each part has its own body. Removing a part releases its connections first.
Calling `build_cart` again makes a fresh cart with fresh parts and links.
The `Arm` and `Cart` dataclasses simply give those parts useful names.

**Try this:** change the wheel size, or shorten the chain by changing `range(7)`.
Puppet poses still work as before; these machines use separate physical actors.
