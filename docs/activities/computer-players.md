# Let the computer play

[Home](../index.md) · [Activities](index.md)

There are two useful kinds of automation:

| Character | Use |
| --- | --- |
| A monster patrolling a platform | Its normal movement script or update function |
| A computer racer using the player's driving rules | An automated gamepad |

A bot chooses **controls**. The game still decides how those controls move its
character. That means the computer follows the same movement and attack rules.

In a game with an existing `hero`, `opponent`, and `stage`, add:

```python
from plocks import Event, GamepadButton, GamepadInput, Stage

computer = stage.gamepads[1]


@stage.on_bot(gamepad=computer)
def choose_controls(event: Event[Stage, float]) -> GamepadInput:
    # Approach the hero. Press A when close enough to attack.
    distance = hero.x - opponent.x
    steering = 0.0 if abs(distance) < 20 else (1.0 if distance > 0 else -1.0)
    buttons = frozenset({GamepadButton.A}) if abs(distance) < 30 else frozenset()
    return GamepadInput(buttons=buttons, left_stick=(steering, 0.0))
```

Your ordinary update function reads `computer.left_stick`, and
`opponent.on_button_down(...)` handles its attack. Holding A fires once unless
the attack listener has `repeat=...`, just like a human controller.

Register the bot before `stage.run()`. It pauses with the game. The same slot
cannot also belong to a remote player. Bots need no networking installation.

A patrolling enemy does **not** need a gamepad. Keep its ordinary script:

```python
patrol = enemy.repeat()
patrol.glide_by(x=100, seconds=1)
patrol.glide_by(x=-100, seconds=1)
enemy.on_start(patrol)
```

For a physical enemy, use body velocity or forces in its update function instead
of glides. Choose the simplest behavior that fits your character.
