# 🏃 Temple Trail

A Temple Run-style course: grab coins, jump, slide and turn!

## Play

```sh
plocks run temple_run
```

To edit your own copy, run `plocks examples temple_run --copy-to my-game`.
Open that new folder and run `python main.py` there. Keep the `assets` folder.


**Left / Right:** change lanes or turn when it says **NOW**

**Space:** jump · **Down:** slide · **R:** restart

## What you'll learn

- **Sequences:** `jump` and `slide` are scripts made of small steps.
- **Dictionaries:** Choose a costume by name, such as `"coin"`.
- **Perspective:** Shrink faraway objects; reveal the next path after a turn.

Release a key before pressing it again. Finish one jump or slide before the next.
Turn when prompted: a wrong or missed turn ends the run. Coins are optional;
the course ends at distance 1900. It looks 3D, but uses flat pictures.

## Make it yours

1. Put three coins in a row in your favourite lane.
2. Add a corner to `course`; keep rows in distance order and before 1900.
3. Replace the runner PNGs, keeping their image sizes the same.

**Your own project?** Copy this whole folder, keep `assets/` beside `main.py`,
and run `python main.py` with Plocks installed. From another folder, use
`python path/to/the/game/main.py` or `plocks run path/to/the/game`.
