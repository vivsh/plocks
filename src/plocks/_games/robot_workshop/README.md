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

**Python ideas:** hinges, angular limits, motors, articulated parts, dataclasses and construction functions. Pictures are in `assets/` beside `main.py`.

**Try this:** change one speed, picture or distance. Save, run, and see what changed!

[More activities](../../../../docs/activities/index.md)
