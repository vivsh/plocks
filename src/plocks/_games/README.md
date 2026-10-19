# 🎮 Pick a game, make it yours

Every example comes with a small game, ready-made pictures and short comments in `main.py`.
They are included when you install Plocks; no repository checkout is needed.
**Start with Sky Steps.** You don't need to understand every line before changing one thing!

```sh
plocks examples
plocks run platformer
```

| Game | What you'll do | What you'll learn |
| --- | --- | --- |
| [Dino Dash](dino_run) | Jump cacti and duck birds | Beginner lessons, scores, restart |
| [Asset Workshop](asset_workshop) | Play with your exported art | Tiled, Pixelorama, two-player controls |
| [Sky Steps](platformer) | Jump and ride a lift | Physics, scripts, checkpoints |
| [Beat Blocks](geometry_dash) | Time your jumps | Speed, gravity, crash checks |
| [Scrolling World](scrolling_world) | Paint a big world | Tile grids, layers, camera and parallax |
| [Coin Quest](mario) | Collect coins and reach the flag | Lists, tile collisions, scoring |
| [Temple Trail](temple_run) | Jump, slide and turn | Sequences, costume changes, perspective |
| [Snake Run](snake_run) | Eat apples and grow | Position history, loops, perspective |
| [Fruit Slice](fruit_ninja) | Swipe fruit, avoid bombs | Random choices, mouse input, geometry |
| [Jungle Run](jungle_run) | Run, jump and shoot | Health, bullets, several actions at once |

## Read the code in small bites

- **Setup at the top** makes the stage, pictures and characters before their controls.
- **Functions underneath** respond to keys and the mouse. Their `@` lines connect the controls.
- **`update(event)`** moves the game forward one small step; `event.data` is time in seconds.
- **`draw(canvas)`** puts scores and instructions on top.
- **The final `if __name__ == "__main__":`** starts the stage when you run the file.

You'll use variables to remember things, `if` to choose, `for` to repeat, and
functions to name jobs. Lists keep groups of objects; dictionaries find pictures
by name. `global score` lets a function change the score made at the top of the file.
You do not need `global` to change `hero.x` or add an item to a list.
Importing an example prepares its game objects without opening the window.
The harder games explain their extra maths beside the code.

## Take a game with you

Run `plocks examples platformer --copy-to my-game` to make your own copy. Keep `assets/` beside `main.py`.
With Plocks installed, run `python main.py` there. From another folder, use
`python path/to/the/game/main.py` or `plocks run path/to/the/game`.
The example finds `assets/` beside its own `main.py`.

Change one thing, play again, then try a challenge in that game's README.
These are original mini-games inspired by familiar styles. Snake Run and Temple
Trail use 2D pictures to look 3D. Controls use a keyboard or mouse, not touch.


## Try a new idea

- [Maze Quest](maze_quest/README.md): click routes, collect coins and try a following camera.
- [Swing Lab](swing_lab/README.md): release a swinging ball from its rope.
- [Robot Workshop](robot_workshop/README.md): build arms, wheels, springs and chains.
