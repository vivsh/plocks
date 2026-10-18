# 6. Try your next idea

[Home](../index.md) · [Dino Dash course](index.md)

You made a game! Now try one new trick. These labs are already inside your
[Dino Dash download](assets.md). Run one at a time from the `dino_run` folder.

## Make your character choose

```sh
python labs/scripts.py
```

1. Press Space to start a trip with talking.
2. Hold Up until the trip ends. Does the reply change?
3. Press H to hop, or R to return home.

A **condition** is a question with a yes/no answer. This script asks whether Up is
held when it reaches the choice. Try another button in
`GamepadDown(GamepadButton.UP, gamepad=stage.gamepads[0])`.
[Make your own script](../activities/movement.md).

## Make a Puppet wave

```sh
python labs/art.py
```

Watch a dinosaur change costumes, a stick person wave, and a little rig bend.
A **Puppet** has parts joined at pivots, like a paper puppet with fasteners.
Its **pose** says which way the joints turn.

Try changing `60` in the waving pose to `90`.
For your own flipbook pictures, try [Pixelorama](../art/pixelorama.md).

## Give coins to two players

```sh
python labs/messages.py
```

Click either dinosaur. Or hold Space for the first, Enter for the second.
A/D and Left/Right move them.

A **broadcast** is a message your game sends. Here it carries how many coins to
add. A named function receives it and changes the dinosaur's memory.
`to=event.target` sends the reward only to that dinosaur. Without `to`, both
matching receivers hear it.

Try changing the reward from `1` to `5` in the `clicked` function.
Want to understand the memory? [Try the coin-counting activity](../activities/memory.md).

## Keep exploring

[Choose a small activity](../activities/index.md), [paint a world](../art/tiled.md),
or [pick another game](../../src/plocks/_games/README.md). Change one thing and play again!
