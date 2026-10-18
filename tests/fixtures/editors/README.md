# Reproducible editor fixtures

Tools: **Tiled 1.12.2** macOS and **Pixelorama v1.2.2-stable** (Godot 4.7.2).
These tools are not test/runtime dependencies. Committed exports keep ordinary
pytest independent of GUI installations.

Hero artwork comes from this repository's `src/plocks/_games/platformer/assets/hero.png`.
The three frame-corner markers are red, green, blue; the frame multipliers are
1, 2, 1 at 10 FPS, tagged `walk`. `hero.pxo` is the native project. Pixelorama's
own exporter produced the PNG/JSON in `../games/integrations_proof/assets/`:

```sh
Pixelorama --headless --quit -- --spritesheet --json --output hero.png hero.pxo
```

`hero_vertical.pxo` changes ordinary packing to orientation 1, two lines. Its
adjacent PNG/JSON were exported with the same command and matching filenames.
Both settings preserve frame order and 0.1/0.2/0.1-second holds. Headless Godot
prints shader-compiler warnings with its dummy renderer; the exports were verified.

`jungle.tmx` references the repository ground artwork and has a named point.
Tiled itself produced `../games/integrations_proof/assets/jungle.tmj`:

```sh
Tiled --export-map jungle.tmx ../games/integrations_proof/assets/jungle.tmj
Tiled --export-map flips.tmx flips.tmj
tmxrasterizer --no-smoothing flips.tmx flips-reference.png
```

`corners.png` is an asymmetric four-color tile. `flips.tmx` contains every square
H/V/diagonal combination. Tests compare the importer against Tiled's rasterizer
reference, rather than inferring transform correctness from the same formula.
TMX/PXO source projects are provenance; runtime imports consume JSON and PNG only.
