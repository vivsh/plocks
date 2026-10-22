# Say “You won!”

[Home](../index.md) · [More activities](index.md)

An **alert** puts a message and a button above the game. Gameplay pauses while
the player reads it. The window keeps drawing, so its button still works.

Try the [complete health game](panels.md), then change its alert:

```python
stage.alert("You found all the coins!", level=AlertLevel.SUCCESS)
```

Call `alert` from a running game's event handler. To show instructions at startup:

```python
@stage.on_start
def instructions(event: Event[Stage, None]) -> None:
    stage.alert("Find four coins. Avoid the robot!")
```

## Choose a level

| Level | Example |
| --- | --- |
| `AlertLevel.INFO` | Instructions; this is the default |
| `AlertLevel.WARNING` | “Low health!” |
| `AlertLevel.SUCCESS` | “Level complete!” |
| `AlertLevel.ERROR` | “Game over!” |

The level changes the accent color and heading. It does not change the game rules.
The theme has matching `info_color`, `warning_color`, `success_color` and `error_color`.

## Choose what happens next

Use `button_text="Play again"` to rename OK. `on_close=play_again` calls your
ordinary function after dismissal, as in the health game. Its event contains the
stage as `target` and `source`, and `None` as `data`.

Click the alert button or press logical gamepad A (Space for player one by default).
Only one alert can be open. Other game clicks and button events are ignored
while it is open; the dismissal cannot click through to the game. Held controls
keep their normal physical state, so release movement controls before continuing.
An alert preserves an earlier manual pause. Closing the game discards it without
running `on_close`.

Messages wrap to fit; very long messages are shortened. Use a short sentence or two.

[Back to screen controls](ui.md)
