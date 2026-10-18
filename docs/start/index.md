# Set up and play

[Home](../index.md)

**Goal:** get one game running. Ask a grown-up to help with these steps once.

## 1. Get ready

You need **Python 3.12 or newer**, an editor such as VS Code, and the
[Plocks project](https://github.com/vivsh/plocks). Download and unzip the project,
or use a copy you already have. Open a terminal inside its main folder.

## 2. Make a place for Plocks

A **virtual environment** keeps this project's tools together.

```sh
python -m venv .venv
```

Switch it on using the command for your computer:

| Computer | Command |
| --- | --- |
| macOS / Linux | `source .venv/bin/activate` |
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |

If Windows blocks that command, ask a grown-up for help.

## 3. Install and play

Still inside the Plocks folder, run:

```sh
python -m pip install -e .
plocks run examples/platformer
```

Use the **arrows** to move and **Space** to jump. Can you reach the gold flag?
Close the game window before starting another game.

Plocks is not on PyPI yet, so install from this project folder as shown.
It already includes the tools it needs; you do not need a separate pygame install.

**Next:** [build Dino Dash](../dino-run/index.md), or
[start with Scratch ideas](from-scratch.md).

**Stuck?** [Check these quick fixes](../help/index.md).
