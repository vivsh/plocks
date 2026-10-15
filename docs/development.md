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

Browser acceptance scripts in `tests/browser/` are Playwright CLI run-code templates.
`proof.js` checks the minimal project served at loopback port 8461; `world.js` checks
the combined project under `/animated_world/dist/web/` at port 8462. Replace their
explicit template tokens before passing them to `playwright-cli run-code`. They
create fresh contexts, optionally block every external origin, and exercise real
input, audio occurrences, animation, pointer scaling, and cleanup. No test hooks
are added to production. Run them serially in headed browsers because focus loss
intentionally suspends simulation. Browser installations must match the CLI.

The configured CI matrix covers Windows/macOS/Linux on Python 3.12/3.13/3.14 and
the minimum pygame-ce/Pillow combination on 3.12. Browser engines, real audio, and
Pylance hovers require separate checks; unit tests do not prove those paths.

`blocks.js` exercises the 0.2 movement gate using `/cdn/` and `/self/` at port 8462.
Keep separate copies of each built site under those paths. It blocks all external
origins in self-contained mode and checks key blocks, async handlers and pause.

`script_failures.js` checks original tracebacks and complete cleanup after an
advanced script or typed message factory fails. `startup_timing.js` measures cold
and repeated startup. Both expect the combined site's two builds at `/world-cdn/`
and `/world-self/` on port 8462. Self-contained request routing disables the HTTP
cache; its repeated visit measures a warm browser/compiler, not cached transfers.

Strict Pyright keeps type diagnostics enabled. Three non-type diagnostics are
disabled explicitly: private access across cooperating implementation modules,
unused private functions that are imported elsewhere, and runtime checks that
remain useful for untyped callers. Unknown-type diagnostics remain enabled.

`bubbles.js` exercises the dialogue example's two builds at `/cdn/` and `/self/`
on port 8463. It waits for the actual Python driver, then verifies displayed text,
independent movement, pause, replacement and cleanup. `native_bubbles.py` posts
native SDL events to the same example. `measure_bubbles.py` measures local dialogue
rendering with 1/10/100 visible speakers; do not compare dummy-driver timing with
native presentation timing as if they measure the same thing.
