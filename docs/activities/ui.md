# Put a score and buttons on screen

[Home](../index.md)

**Goal:** show information without a drawing callback.

## 1. Make a playground

```sh
plocks examples maze_quest --copy-to menu-game
cd menu-game
```

Open `main.py`. Find the score label and health bar. Change their colours or positions.

## 2. Read the controls

A label remembers the words it displays:

```python
score = Label("Coins: 0", position=(-225, 172))
stage.add(score)
score.text = "Coins: 1"
```

A bar shows a value from zero to its maximum:

```python
health = ProgressBar(value=100, maximum=100)
stage.add(health)
health.value = 75
```

These positions are on the screen, so the world camera never moves them.
By default, position is the control's center. Use the existing `Anchor` names
to choose another point:

```python
score = Label("Coins: 0", position=(-220, 160), anchor=Anchor.TOP_LEFT)
```

Import `Anchor` from `plocks`. Now a longer score keeps its top-left corner in
place. All nine anchors work with labels, bars, buttons and panels.

## 3. Try the pause button

Run `python main.py` and press P. Click Continue, or press Space to activate it.
The game uses `stage.focus(resume)` to give the menu keyboard/gamepad control.
Directional buttons choose a button; A activates it. Mouse presses work too.

Button functions receive `Event[Button, None]`. They can change game objects,
broadcast messages or resume the stage. Hiding the focused button releases focus.

**Try this:** change the Continue button's text or `text_size`.
Your existing `Canvas` drawings still work above these ordinary controls.

## Build your own menu

[Put controls in a colored Panel](panels.md) and give them a matching `UITheme`.
[Show an alert](alerts.md) for “Game over!” or “You won!”—it appears above the game
and pauses play until the player acknowledges it.

[Next: panels and styling](panels.md)
