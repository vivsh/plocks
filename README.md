# Plocks

Small, typed Python games for children moving on from Scratch. Reusable blocks, sprites and articulated Puppets,
ordinary Python functions, informative editor tooltips, and the same game on desktop
and in a shareable browser page. Python 3.12 or newer is required.

Plocks is under development and has not been published to PyPI. Install from this source checkout.

## Install and try it

From this checkout, create a virtual environment and install the local package:

```sh
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e '.[web]'
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

## Share a game

```sh
plocks serve examples/animated_world
plocks build examples/animated_world
plocks build examples/animated_world --self-contained
```

`serve` builds a loopback preview. `build` creates `dist/web/` and
`dist/game-web.zip` inside the game folder. Upload the directory or unpack the ZIP
on a static HTTP(S) host, including beneath a URL prefix. Nothing is uploaded
automatically. Opening `index.html` through `file://` is unsupported.

The default website uses a pinned CDN runtime. `--self-contained` includes the
runtime and supporting resources for playback without external requests. Building
either mode requires network access to verify pinned artifacts. Transfer size
depends on the game and HTTP compression: the 0.2 combined demo measured about
24 MB from an uncompressed self-contained server and 12.3 MB with the CDN runtime.
These are sample cold loads, not size guarantees. Measure your own build.

## Learn more

- [Dialogue](docs/dialogue.md): speech, thoughts, changing text, and cancellation.
- [Tutorial](docs/tutorial.md): blocks, costumes, messages, and Puppets.
- [API guide](docs/api.md): coordinates, composition, messaging, tiling, and lifecycle.
- [Browser sharing](docs/sharing.md): configuration and portability limits.
- [Development](docs/development.md): typing, tests, and distribution checks.
- [Migration](docs/migration.md): moving projects from the 0.1 API.

The library ships `py.typed`. Select the virtual environment in VS Code, enable
Pylance, and hover over methods or enums. No mypy plugin or injected globals are
required.
