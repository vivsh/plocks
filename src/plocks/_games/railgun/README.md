# Railgun Range

Blast brick cover and zap three robots with an instant blue beam.

```sh
plocks run railgun
```

**Arrows:** walk · **Space / gamepad A:** jump · **X / gamepad B:** fire · **R:** reset

Hold X for repeated shots. Destroy a top brick, zap the robot behind it, and jump
over the low brick. The camera follows you through the range.

To edit: `plocks examples railgun --copy-to my-railgun`, then run
`python my-railgun/main.py`. Images and the original Plocks sound stay beside the code.

- `raycast()` finds the first object along the aim line. The firing function applies damage.
- Three thin image sprites make the blue glow and white core. `remove_after()` ends the flash.
- Beams use `BodyType.NONE`, so they stay out of physics and future ray queries.
- `on_hit` handles real hero/wall/robot body contact using `Event[Sprite, Collision]`.
- A brief brightness animation flashes the hero on contact; it does not change damage.
- `on_touch(other)` remains a visual-overlap trigger. A ray query emits no collision event.

Try a longer flash, a wider beam, or a tougher robot that needs two shots.
