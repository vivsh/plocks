# Duck under a ceiling

[Home](../index.md) · [More activities](index.md)

Save [this little game](crouching.py) and run `python crouching.py` with Plocks installed.
Use **Left / Right** to walk and hold **Down** to duck under the blue ceiling.
Let go of Down: your hero stands when there is enough room!

Both pictures use `Anchor.BOTTOM_CENTER`. That means the sprite's position is its
feet, so changing pictures keeps the feet in place.

```python
hero.image = crouching  # The invisible physics box becomes shorter too.
```

Before standing, check the space above:

```python
if hero.body.can_fit_image(standing):
    hero.image = standing
```

The check does not change anything. Calling it again each update lets the hero
stand once they leave the ceiling. Changing an image directly always changes it;
Plocks does not refuse it for you.

**Want a steady hit box for every animation frame?** Set it explicitly:

```python
hero.body.shape = Box(24, 60, center=(0, 30))
```

Import `Box` from `plocks`. This box starts at the feet and stays fixed when images
change. `hero.body.use_actor_shape()` makes the body follow pictures again;
`hero.body.auto_shape` tells you whether it does.

Puppets also follow their poses and part images, using one box around all parts.
Use a fixed box when waving arms should not change collisions. For a proposed
Puppet pose, use `person.body.can_fit_pose(pose)`; for your own box or circle,
use `body.can_fit_shape(shape)`.

Picture bounds include transparent padding. Crop or trim unwanted padding first.
Automatic sizing follows animation in game time, so pausing pauses both.

**Try it:** make the ceiling longer, or change the walking speed from 120 to 160.
