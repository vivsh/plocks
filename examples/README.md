# 🎮 Pick a game, make it yours

Each folder has a small game, ready-made pictures and short comments in `main.py`.
**Start with Sky Steps.** You don't need to understand every line before changing one thing!

```sh
plocks run examples/platformer
```

| Game | What you'll do | What you'll learn |
| --- | --- | --- |
| [Sky Steps](platformer/) | Jump and ride a lift | Physics, recipes, checkpoints |
| [Beat Blocks](geometry_dash/) | Time your jumps | Speed, gravity, crash checks |
| [Scrolling World](scrolling_world/) | Paint a big world | Tile grids, layers, camera and parallax |
| [Coin Quest](mario/) | Collect coins and reach the flag | Lists, tile collisions, scoring |
| [Temple Trail](temple_run/) | Jump, slide and turn | Sequences, costume changes, perspective |
| [Snake Run](snake_run/) | Eat apples and grow | Position history, loops, perspective |
| [Fruit Slice](fruit_ninja/) | Swipe fruit, avoid bombs | Random choices, mouse input, geometry |
| [Jungle Run](jungle_run/) | Run, jump and shoot | Health, bullets, several actions at once |

## Read the code in small bites

- **Setup at the top** makes the stage, pictures and characters before their controls.
- **Functions underneath** respond to keys and the mouse. Their `@` lines connect the controls.
- **`update(dt)`** moves the game forward one small step; `dt` is time in seconds.
- **`draw(canvas)`** puts scores and instructions on top.
- **The final `if __name__ == "__main__":`** starts the stage when you run the file.

You'll use variables to remember things, `if` to choose, `for` to repeat, and
functions to name jobs. Lists keep groups of objects; dictionaries find pictures
by name. `global score` lets a function change the score made at the top of the file.
You do not need `global` to change `hero.x` or add an item to a list.
Importing an example prepares its game objects without opening the window.
The harder games explain their extra maths beside the code.

## Take a game with you

Copy the **whole game folder** into your project. Keep `assets/` beside `main.py`.
With Plocks installed, run `python main.py` there, or
`python path/to/the/game/main.py` from another folder.

Change one thing, play again, then try a challenge in that game's README.
These are original mini-games inspired by familiar styles. Snake Run and Temple
Trail use 2D pictures to look 3D. Controls use a keyboard or mouse, not touch.
