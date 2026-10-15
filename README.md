# Plocks

Small, typed Python games for children moving on from Scratch. Reusable blocks, sprites and articulated Puppets,
ordinary Python functions, and informative editor tooltips. Python 3.12 or newer is required.

Plocks is under development and has not been published to PyPI. Install from this source checkout.

## Install and try it

From this checkout, create a virtual environment and install the local package:

```sh
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
plocks run examples/animated_world
```

Arrows walk, J jumps, Space plays a sound, P pauses, and clicking near the ground edits tiles.
The package uses pygame-ce; avoid installing the separate `pygame` distribution in
the same environment.

## Your first game

Save this as `main.py`. Run `python main.py` from its folder or
`plocks run path/to/my-game`.

```python
from PIL import Image
from plocks import GlideBy, Key, Sprite, Stage

stage = Stage()
cat = Sprite(Image.new("RGBA", (32, 32), "orange"))
stage.add(cat)
stage.on_key_down(Key.RIGHT, cat, GlideBy(x=60, seconds=0.4))

stage.run()
```

Coordinates start at the center. Positive x goes right; positive y goes up. Durations use simulated seconds; pauses freeze motion. `run()` belongs at the end of the entry script.
Sprites render automatically. Constructing one does not add it to a stage or open
a window.

## Learn more

- [Dialogue](docs/dialogue.md): speech, thoughts, changing text, and cancellation.
- [Tutorial](docs/tutorial.md): blocks, costumes, messages, and Puppets.
- [API guide](docs/api.md): coordinates, composition, messaging, tiling, and lifecycle.
- [Development](docs/development.md): typing, tests, and distribution checks.
- [Migration](docs/migration.md): moving projects from the 0.1 API.

The library ships `py.typed`. Select the virtual environment in VS Code, enable
Pylance, and hover over methods or enums. No mypy plugin or injected globals are
required.
