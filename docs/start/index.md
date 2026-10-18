# Set up and play

[Home](../index.md)

**Goal:** get one game running. Ask a grown-up to help with these steps once.

## 1. Get ready

You need **Python 3.12 or newer**, an editor such as VS Code, and a terminal.
Choose a folder for your games. You do not need to download or update the Plocks
repository yourself.

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

In your terminal, run:

```sh
python -m pip install --upgrade "https://github.com/vivsh/plocks/archive/refs/heads/main.zip"
plocks examples
plocks run platformer
```

Use the **arrows** to move and **Space** to jump. Can you reach the gold flag?
Close the game window before starting another game.

Plocks is not on PyPI yet, so this installs directly from GitHub. Its example
games, pictures and sounds are included. Run them from any folder.
It already includes the tools it needs; you do not need a separate pygame install.

## 4. Make your own copy

```sh
plocks examples platformer --copy-to my-game
cd my-game
python main.py
```

Now you can edit `main.py`. Keep `assets` beside it. Copying needs a new folder;
it will not overwrite a game you already have.

**Next:** [build Dino Dash](../dino-run/index.md), or
[start with Scratch ideas](from-scratch.md).

**Stuck?** [Check these quick fixes](../help/index.md).
