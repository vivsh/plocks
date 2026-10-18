# Asset Workshop

Play with a level from **Tiled** and pictures from **Pixelorama**.

```sh
plocks run examples/asset_workshop
```

| Player | Move | Jump | Speak (hold it!) |
| --- | --- | --- | --- |
| One | A / D | Space | F |
| Two | Left / Right | Enter | Right Shift |
| Controller | Left stick | A | B |

**E** changes a ground tile. Player two uses Nintendo face-button labels.
Both players use the built-in keyboard defaults, even without controllers.

Try changing the jump height or giving each player a different speed.
The jump is a movement script: it returns to where it started. To land on
platforms, use physics as in Sky Steps; these glides do not resolve collisions.

Learn to [export your own artwork](../../docs/art/index.md) or
[choose controller and keyboard controls](../../docs/activities/controls.md).
