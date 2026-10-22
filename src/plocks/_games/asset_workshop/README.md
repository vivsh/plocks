# Asset Workshop

Play with a level from **Tiled** and pictures from **Pixelorama**.

```sh
plocks run asset_workshop
```

To edit your own copy, run `plocks examples asset_workshop --copy-to my-game`.
Open that new folder and run `python main.py` there. Keep the `assets` folder.


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

Learn to [export your own artwork](https://github.com/vivsh/plocks/blob/main/docs/art/index.md) or
[choose controller and keyboard controls](https://github.com/vivsh/plocks/blob/main/docs/activities/controls.md).

## Screen controls

A Panel keeps both players’ control hints together. Labels show the words without a drawing function.
