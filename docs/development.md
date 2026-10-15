# Development and validation

Install with `python -m pip install -e '.[dev,web]'` in a Python 3.12+ environment.

```sh
ruff check src tests examples
ruff format --check src tests examples
mypy src tests examples
pyright
pyright --verifytypes plocks --ignoreexternal
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy pytest -q
```

On Windows PowerShell, set the two driver variables using `$env:NAME="dummy"`
before pytest. Real desktop/display/audio checks should also run with them unset.
Dummy drivers prove lifecycle behavior, not audible hardware output. Negative type
fixtures verify callbacks, actor/block compatibility, invariant message payloads,
factories, assets, coordinates, pose angles, and rejection of async update/draw.

Build distributions with `python -m build`. Install the wheel into an isolated
environment outside this checkout and repeat type checks there. Wheel and source
distribution must contain `py.typed`, browser templates, and the pinned runtime
inventory. Select the intended environment on PATH for Pyright verification.

Browser acceptance scripts in `tests/browser/` exercise input, audio, animation,
pointer scaling, failures, and cleanup. Run them serially because focus loss
intentionally suspends simulation. Browser installations must match the Playwright CLI.

The configured CI matrix covers Windows/macOS/Linux on Python 3.12/3.13/3.14 and
the minimum pygame-ce/Pillow combination on 3.12. Browser engines, real audio, and
Pylance hovers require separate checks; unit tests do not prove those paths.

Strict Pyright keeps type diagnostics enabled. Three non-type diagnostics are
disabled explicitly: private access across cooperating implementation modules,
unused private functions that are imported elsewhere, and runtime checks that
remain useful for untyped callers. Unknown-type diagnostics remain enabled.

`native_bubbles.py` posts native SDL events to the dialogue example.
`measure_bubbles.py` measures local dialogue rendering with 1/10/100 visible
speakers; do not compare dummy-driver timing with native presentation timing as
if they measure the same thing.
