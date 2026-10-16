# Plocks

<img src="src/plocks/assets/icon.png" alt="Plocks: a cheerful orange block with green sneakers" width="180">

Small, typed Python games for children moving on from Scratch. Create sprites and
Puppets, give them actions, and build reusable recipes with ordinary Python methods.
Editor tooltips explain coordinates, timing, and behavior. Requires Python 3.12+.

Plocks is under development and has not been published to PyPI. Install from this checkout.

## Install and try it

```sh
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
plocks run examples/animated_world
```

Arrows walk, J jumps, Space plays a sound, P pauses, and clicking near the ground edits tiles.
Plocks uses pygame-ce; avoid installing the separate `pygame` distribution in the same environment.

## Your first game

Save this as `main.py`. Run `python main.py` from its folder, or `plocks run path/to/my-game`.

```python
from PIL import Image
from plocks import Key, Sprite, Stage


def main() -> None:
    stage = Stage()
    cat = Sprite(Image.new("RGBA", (32, 32), "orange"))
    stage.add(cat)

    hop = cat.sequence()
    hop.glide_by(y=60, seconds=0.3)
    hop.glide_by(y=-60, seconds=0.3)
    cat.on_key_down(Key.SPACE, hop)

    stage.run()


if __name__ == "__main__":
    main()
```

Coordinates start at the center. Positive x goes right; positive y goes up.
Commands return immediately and run in the game loop. Pausing freezes simulated time.
Sprites render automatically after `stage.add(...)`.

Physics is included in the default installation. Try falling, jumping, and moving platforms:

```sh
plocks run examples/physics_proof
```

## Learn more

- [Tutorial](docs/tutorial.md): sequences, repetition, messages, and Puppets.
- [Dialogue](docs/dialogue.md): speech, thoughts, and changing text.
- [Physics](docs/physics.md): bodies, terrain, forces, and moving platforms.
- [API guide](docs/api.md): coordinates, action lifetimes, events, and assets.
- [Migration](docs/migration.md): upgrading from the blocks API to 0.3.
- [Development](docs/development.md): local installation, typing, and tests.

Select your virtual environment in VS Code and enable Pylance. The package includes
`py.typed`; no mypy plugin or injected globals are required.
