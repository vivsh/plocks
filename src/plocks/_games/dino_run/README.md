# Dino Dash 🦖

Jump over cacti and rocks. Duck the birds. Grab coins and beat your best score!
This is our own colourful runner, inspired by Chrome's offline dinosaur game.

```sh
plocks run dino_run
```

To edit your own copy, run `plocks examples dino_run --copy-to my-game`.
Open that new folder and run `python main.py` there. Keep the `assets` folder.


| Control | Action |
| --- | --- |
| Space / Up / controller A / left click | Jump |
| Down / S / F / controller B | Duck while held |
| P | Pause / continue |
| R | Start a new run |

Start with the [step-by-step course](https://github.com/vivsh/plocks/blob/main/docs/dino-run/index.md).
Run `01_hello.py`, `02_controls.py`, then `03_jump.py` inside this folder before
trying `main.py`. Each checkpoint is a complete program, not a file to import.
Copy the entire folder to use it elsewhere; pictures stay beside the scripts.

**Make it yours:** change the jump impulse `460`; change the spawn wait `1.4`;
change the `200` score that unlocks birds. Try one change at a time.

The best score lasts for this window's session. Physics handles falling and landing;
scripts handle spawn timing. No Pillow code is needed.

The dinosaur runs forwards and `stage.follow(...)` follows it. Obstacles use
`BodyType.STATIC`; floor tiles and coins stay in world coordinates. The camera
makes them scroll past! `extend_ground()` adds floor ahead and removes sections
behind, so a long run does not keep every old tile.

## Screen controls

Labels show your score, coins and best run. A Panel holds the Continue / Play again button; P and R still work.
