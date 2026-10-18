<p align="center">
  <img src="src/plocks/assets/icon.png" alt="Plocks: a cheerful orange block with green sneakers" width="160">
</p>

<h1 align="center">Plocks</h1>
<p align="center"><strong>Small games. Real Python. Your rules.</strong></p>

Moving on from Scratch? Build desktop Python games with ready-made pictures and simple
movement scripts. Start with an example, then make it your own!

## 🎮 Play your first game

You need **Python 3.12+** and this project. Ask a grown-up for setup help if needed.

```sh
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -e .
plocks run examples/platformer
```

**Arrows** move · **Space** jumps · **R** restarts. Can you reach the gold flag?

Install from this checkout; Plocks is not on PyPI yet. It includes pygame-ce—
keep the separate `pygame` package out of this environment.
Games run in their own desktop window.

## 📚 Learn step by step

[Start learning here](docs/index.md): setup, the dinosaur course, small activities, artwork and help.

| Start where you are | Your guide |
| --- | --- |
| New to Python | [Build Dino Dash, one small step at a time](docs/dino-run/index.md) |
| Coming from Scratch | [Turn familiar blocks into Python](docs/start/from-scratch.md) |
| Want your own artwork | [Draw with Pixelorama](docs/art/pixelorama.md) |
| Want your own level | [Paint a world with Tiled](docs/art/tiled.md) |
| Need ready-made pictures | [Download the dinosaur sprite pack](docs/dino-run/assets.md) |
| Curious about more tools | [Choose a small activity](docs/activities/index.md) |

## 🗺️ Pick an adventure

| Game | Your mission | New ideas to try |
| --- | --- | --- |
| [Dino Dash](examples/dino_run) | Jump cacti, duck birds and collect coins | A complete beginner course, physics, scores, restart |
| [Sky Steps](examples/platformer) — start here | Ride a lift and reach the flag | Physics, repeating moves, checkpoints |
| [Beat Blocks](examples/geometry_dash) | Jump over spikes | Timing, gravity, crash checks |
| [Asset Workshop](examples/asset_workshop) | Use Tiled and Pixelorama artwork | Exported levels, animation, two-player controls |
| [Scrolling World](examples/scrolling_world) | Explore and paint a world | Tile grids, layers, a following camera |
| [Coin Quest](examples/mario) | Grab coins and stomp enemies | Lists, solid tiles, scoring |
| [Temple Trail](examples/temple_run) | Jump, slide and turn corners | Movement scripts, costumes, perspective |
| [Dojo Duel](examples/dojo_duel) | Win a two-player martial-arts match | Two sets of keys, scripts, health and hit checks |
| [Sunset Sprint](examples/sunset_sprint) | Steer past three computer cars | Acceleration, steering, collisions and lap maths |
| [Snake Run](examples/snake_run) | Eat apples and grow a tail | Remembering positions, size and distance |
| [Fruit Slice](examples/fruit_ninja) | Swipe fruit, dodge bombs | Mouse input, randomness, swipe maths |
| [Jungle Run](examples/jungle_run) | Run, jump and shoot robots | Bullets, health, several things moving together |

Each `main.py` has short comments. Start small; Fruit Slice and Jungle Run are
stretch challenges. Copy a whole game folder into your project, including `assets/`,
and run `python main.py` with Plocks installed. From another folder, use
`python path/to/the/game/main.py` or `plocks run path/to/the/game`.

## ✨ Make a character hop

Copy `examples/platformer/assets` beside a new `main.py`. Save this code and run
`python main.py` there.

```python
from plocks import Key, Sprite, Stage

# Make the stage and hero before connecting their controls.
stage = Stage()
hero = Sprite("assets/hero.png")
stage.add(hero)

# A sequence is a script: go up, then come back down.
hop = hero.sequence()
hop.glide_by(y=60, seconds=0.3)
hop.glide_by(y=-60, seconds=0.3)


# Bind the script directly. Extra presses are ignored until this hop finishes.
hero.on_key_down(Key.SPACE, hop)

# Start only when we run this file directly.
if __name__ == "__main__":
    stage.run()
```

Press **Space**! Change `60` to `100` in both moves for a bigger hop.
**Coordinates:** the middle is `(0, 0)`; x goes right and y goes up.

Each example puts setup first, functions underneath, and the guarded `stage.run()`
last. Importing the file prepares its pictures and game objects, but does not start
its window. Use `global score` to reassign the shared score inside a function;
changing `hero.x` or adding to a list does not need `global`.

## 🧰 Python tools you'll meet

| Tool | What it does in a game |
| --- | --- |
| Variables and `True` / `False` | Remember a score or whether you have won |
| `if` / `else` | Choose what happens: collect a coin or lose a life |
| Functions (`def`) | Give a job a name, like `jump` or `restart` |
| `for` loops | Do a job for every coin, enemy or tile |
| Lists and tuples | Keep several things together, like coins or an `(x, y)` position |
| Dictionaries | Find a picture by its name, such as `"coin"` |
| Events (`@...`) | Tell Plocks when to call a function: on a key press or each game step |
| `global` | Let a function change a game variable, such as `score`, from the top of the file |
| f-strings (`f"Score: {score}"`) | Put a changing number into words on screen |

**Events:** handlers receive `event.target` (who receives it), `event.source` (who caused it),
and `event.data` (what happened). Broadcast messages use the same Event shape.
**Timing:** an update's `event.data` is one game step's time; speed × time gives movement.
**Type hints:** `: float` means a number with decimals; `-> None` means a function has no result.
**Scripts:** one script can run on several characters; each gets its own turn.
Try [character memory](docs/activities/memory.md), such as
`hero.state.health`. Declare it with a normal Python dataclass and change it in
your functions. Use `stage.state.score` for a shared score.

Make your own pictures with [Tiled and Pixelorama](docs/art/index.md), or give a friend
[gamepad and keyboard controls](docs/activities/controls.md). Hover over Plocks names in your
Python editor for help.

## 🚀 Make it yours

1. Change one speed, colour or picture.
2. Play again and see what changed.
3. Invent a new rule!

Find small challenges in each game's README. These are keyboard/mouse games;
Snake Run and Temple Trail look 3D using flat pictures.
