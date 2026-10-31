# Clone Blaster

Walk, jump and shoot the robot targets. Every shot is a clone!

```sh
plocks run clone_blaster
```

**Arrows:** walk · **Space / gamepad A:** jump · **X / gamepad B:** fire
Hold the fire button to keep shooting. Targets stay put so you can practise.
Jump and shoot above their heads to hit the tile wall. Fire left to see bullets
leave the screen and disappear.

To edit it: `plocks examples clone_blaster --copy-to my-blaster`, then run
`python my-blaster/main.py`. The assets stay beside the code.

## The important bits

- `bullet` is a hidden template. It must stay attached to the stage.
- `bullet.clone()` creates and adds a separate bullet. Do not add it again.
- `event.target` is the bullet receiving a collision event.
- `bullet_clone.remove()` removes that copy. The next shot still uses `bullet`.
- Even hidden originals receive handlers. `is_clone` protects the template.
- Fire belongs to the **hero**; bullets inherit the template's handlers, not the hero's.
- Sensor bullets use overlap events; they do not push the robots.
- `travel_along(speed=520, direction=...)` launches the copy along the hero’s facing direction.

Try changing bullet speed from 520 to 350 or the firing interval from 0.18 to 0.3.
