# Swing Lab

Watch the ball swing, cut its rope, and try again.

```sh
plocks run swing_lab
```

**Controls:** Space or the button cuts the rope. R resets the ball.

To change it:

```sh
plocks examples swing_lab --copy-to my-swing_lab
cd my-swing_lab
python main.py
```

**Python ideas:** physical ropes, fixed anchors, gravity, collision shapes, drawing and buttons. The ball and floor use `Image.circle` and `Image.rectangle`; no picture files are needed.

**Try this:** change the ball's color or the rope's length. Save, run, and see what changed!

[More activities](../../../../docs/activities/index.md)

## Screen controls

A themed Panel holds Cut rope. The hint stays on screen; Canvas still draws the actual rope.
