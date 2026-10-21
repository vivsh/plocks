<p align="center">
  <img src="src/plocks/assets/icon.png" alt="Plocks: a cheerful orange block with green sneakers" width="160">
</p>

<h1 align="center">Plocks</h1>
<p align="center"><strong>Small games. Real Python. Your rules.</strong></p>

**Plocks is a Python game development library for Scratch developers ready for
their next step.** Keep familiar ideas—sprites, images, scripts and broadcasts—
while learning to write Python.

Build desktop games with ready-made pictures, simple controls and helpful editor
hints. Start with a bundled game, change one thing, and see what happens!

## 🧩 Bring your Scratch ideas to Python

| What you want to do | What Plocks gives you |
| --- | --- |
| Bring characters to life | Sprites, [images, grids, named pictures and anchors](docs/art/images.md), speech and thought bubbles, and jointed Puppets |
| Give characters a plan | Movement scripts: glide, wait, repeat and react to events |
| Make characters work together | Broadcasts, typed message data and clones with their own controls |
| Make a ball or block | [Shape images](docs/art/shapes.md) with colors, outlines and anchors—no picture files needed |
| Build a world | Tile maps, automatic camera following, parallax, and Tiled and Pixelorama artwork |
| Jump and land | Built-in physics, moving platforms, and platforms you can jump through from below |
| Solve a maze | [Find a route around walls](docs/activities/navigation.md), then follow it at your chosen speed |
| Collect coins and show progress | [Touch events](docs/activities/touch.md), [labels, health bars and buttons](docs/activities/ui.md) |
| Make a machine | [Ropes, springs, hinges and motors](docs/activities/assemblies.md) joining ordinary characters |
| Play together | Logical gamepads with mapped keys or controllers, plus optional [LAN shared-view play](docs/activities/multiplayer.md) |
| Give the computer a turn | [Automated gamepads](docs/activities/computer-players.md) that use the human player's controls |

Try changes live at an [IPython prompt](#-try-ideas-live-with-ipython), or write a
normal Python file. Both use the same game library.

## 🎮 Play your first game

You need **Python 3.12+**. Ask a grown-up for setup help if needed.

```sh
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install --upgrade "https://github.com/vivsh/plocks/archive/refs/heads/main.zip"
plocks examples
plocks run platformer
```

**Arrows** move · **Space** jumps · **R** restarts. Can you reach the gold flag?

This installs directly from GitHub; no clone or git pull is needed. Plocks is not
on PyPI yet. The examples and pictures come with the install. It includes pygame-ce—
keep the separate `pygame` package out of this environment.
Games run in their own desktop window.

## 🔬 Try ideas live with IPython

Change a character and see what happens straight away—without restarting the game!
With Plocks installed, make a playground and open IPython:

```sh
python -m pip install "ipython>=9,<10"
plocks examples platformer --copy-to playground
cd playground
ipython
```

Enter these lines at the IPython prompt:

```python
from plocks import Sprite, Stage

stage = Stage(background="midnightblue")
hero = Sprite("assets/hero.png")
stage.add(hero)
stage.run(interactive=True)
```

The game stays open and the prompt comes back. Try each line and watch your hero:

```python
hero.x = 100
hero.say("Hello!")
hero.glide_by(x=-100, seconds=1)
```

Try `hero.glide_by?` to read its help.

Use `stage.pause()` to freeze the game, `stage.resume()` to continue, and
`stage.stop()` to close it. After closing, make a new `Stage` to play again.
The game keeps running when you switch to the terminal. Hiding or minimizing its
window pauses it.

Use **terminal IPython** with its normal prompt. This mode opens a desktop window;
notebook cells and `--simple-prompt` aren't supported. Keep commands short: a long
Python command occupies the same thread as the game. Ordinary game files still use
`stage.run()` and work as before.

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
| [Alpine Racer](src/plocks/_games/alpine_racer) | Race five rivals for five minutes | Steering pictures, acceleration, perspective and a circuit map |
| [Maze Quest](src/plocks/_games/maze_quest) | Click a route and collect four coins | Navigation, touch events, camera following and screen controls |
| [Swing Lab](src/plocks/_games/swing_lab) | Cut a swinging ball's rope | Anchors, physics and buttons |
| [Robot Workshop](src/plocks/_games/robot_workshop) | Turn an arm, drive a cart and drop a chain | Hinges, springs, motors and construction functions |
| [Dino Dash](src/plocks/_games/dino_run) | Jump cacti, duck birds and collect coins | A complete beginner course, physics, scores, restart |
| [Sky Steps](src/plocks/_games/platformer) — start here | Jump through a lift and reach the flag | Physics, one-way platforms, repeating moves, checkpoints |
| [Beat Blocks](src/plocks/_games/geometry_dash) | Jump over spikes | Shape images, linked glide actions, crash checks |
| [Asset Workshop](src/plocks/_games/asset_workshop) | Use Tiled and Pixelorama artwork | Exported levels, animation, two-player controls |
| [Scrolling World](src/plocks/_games/scrolling_world) | Explore and paint a world | Tile grids, layers, a following camera |
| [Coin Quest](src/plocks/_games/mario) | Grab coins and stomp enemies | Physics, a following camera, scoring |
| [Temple Trail](src/plocks/_games/temple_run) | Jump, slide and turn corners | Movement scripts, images, perspective |
| [Snake Run](src/plocks/_games/snake_run) | Eat apples and grow a tail | Remembering positions, size and distance |
| [Fruit Slice](src/plocks/_games/fruit_ninja) | Swipe fruit, dodge bombs | Mouse input, randomness, swipe maths |
| [Jungle Run](src/plocks/_games/jungle_run) | Run, jump and shoot robots | Bullets, health, several things moving together |

**The camera is your view of the world.** Scrolling games use
[`stage.follow(...)`](docs/activities/camera.md); tiles and obstacles stay in their
world positions. Arena games keep a fixed view. Temple Trail and Snake Run use
perspective to look 3D. Scores and buttons stay on the screen in every view.
Physics is **off by default**; use `Stage(physics=True)` when you want gravity and
physical collisions.

Each `main.py` has short comments and uses Plocks for timed moves, physical
jumps and camera following. Simple balls and blocks use shape Images; characters
keep their ready-made artwork. Start small; Fruit Slice and Jungle Run are
stretch challenges. Run a bundled game from any folder with `plocks run NAME`.
The older spelling `plocks run examples/NAME` works too.

To change a game, make your own copy:

```sh
plocks examples platformer --copy-to my-game
cd my-game
python main.py
```

Choose a new folder name: Plocks never overwrites an existing game. Your copy
includes its pictures and sounds. `plocks run path/to/my-game` also runs local
projects; an existing local folder takes precedence over a bundled name.

## ✨ Make a character hop

Make the `my-game` copy above, replace its `main.py` with this code, and run
`python main.py` inside that folder. Keep its `assets` folder.

```python
from plocks import GamepadButton, Sprite, Stage

# Make the stage and hero before connecting their controls.
stage = Stage()
hero = Sprite("assets/hero.png")
stage.add(hero)

# A sequence is a script: go up, then come back down.
hop = hero.sequence()
hop.glide_by(y=60, seconds=0.3)
hop.glide_by(y=-60, seconds=0.3)


# Bind the script directly. Extra presses are ignored until this hop finishes.
hero.on_button_down(GamepadButton.A, hop, gamepad=stage.gamepads[0])

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

## 🧬 Make a copy

```python
copy = hero.clone()
copy.position = (100, 0)
```

`clone()` adds the copy to the same stage automatically. Do not call
`stage.add(copy)` afterwards; just change the returned copy's position or settings.

Copies inherit the character's controls and get their own position. With physics
enabled, each gets its own body too.
Use `@hero.on_clone` to start each copy, and `event.target` inside inherited functions.
Remove a copy with `stage.remove(copy)`. Try the [clone activity](docs/activities/clones.md).

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

**Events:** input, update and broadcast handlers receive `event.target` (who receives it),
`event.source` (who caused it),
and `event.data` (what happened). Broadcast messages use the same Event shape.
**Timing:** an update's `event.data` is one game step's time; speed × time gives movement.
**Type hints:** `: float` means a number with decimals; `-> None` means a function has no result.
**Scripts:** one script can run on several characters; each runs independently.
Build a script with `hero.sequence()` or `hero.repeat()`, then start it with
`hero.act(script)`. You can also link individual actions with `after=previous_action`.
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

Find small challenges in each game's README. Use mapped keys or controllers;
Fruit Slice also uses the mouse.
Snake Run and Temple Trail look 3D using flat pictures.
