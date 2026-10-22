# Robot Workshop

Drive a cart, turn the arm and drop a chain.

```sh
plocks run robot_workshop
```

**Controls:** Arrows drive. Hold Space/X to turn the arm. R creates another cart. Click Drop chain to release it.

To change it:

```sh
plocks examples robot_workshop --copy-to my-robot_workshop
cd my-robot_workshop
python main.py
```

**Python ideas:** hinges, angular limits, motors, articulated parts, dataclasses and construction functions. Beams and wheels use shape Images. Existing pictures in `assets/` are there if you want to swap them in.

**Try this:** change a beam's size, a wheel's color or a motor's speed. Save, run, and see what changed!

[More activities](../../../../docs/activities/index.md)

## Screen controls

A themed Panel holds Drop chain. Labels name each machine; Canvas still draws the spring.
