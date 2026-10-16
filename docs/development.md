# Local development

Install the editable package and tools in a virtual environment:

```sh
python -m pip install -e '.[dev,web]'
python -m pytest -q
python -m mypy
pyright
ruff check src tests examples
ruff format --check src tests examples
python -m build
```

`SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy` can be set for headless behavioral
checks. Those checks do not establish native display or audible sound behavior.
`tests/native_actions.py` and `tests/native_physics.py` exercise actual display execution.
Run native/window-focus probes serially: losing focus intentionally suspends the game.

`tests/typing/hover_example.py` is a positive editor fixture. Select the virtual
environment in VS Code/Pylance and inspect completion and hovers there. The negative
fixture is checked by tests. `pyright --verifytypes plocks --ignoreexternal` checks
public type completeness. Validate an installed wheel outside this checkout as well.

Do not install the separate `pygame` distribution alongside pygame-ce. Pymunk is included in
the default installation. Enable simulation explicitly with `Stage(physics=True)`.
No PyPI release is required to develop or run Plocks locally.
