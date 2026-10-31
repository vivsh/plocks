# 🎮 Pick a game, make it yours

Every example comes with a small game, ready-made pictures or simple shapes, and short comments in `main.py`.
They are included when you install Plocks; no repository checkout is needed.
**Start with Sky Steps.** You don't need to understand every line before changing one thing!

```sh
plocks examples
plocks run platformer
```

| Game | What you'll do | What you'll learn |
| --- | --- | --- |
| [Alpine Racer](alpine_racer) | Race five rivals for five minutes | Steering images, speed, perspective and race positions |
| [Maze Quest](maze_quest) | Click routes and collect coins | Navigation, touch events and a following camera |
| [Swing Lab](swing_lab) | Cut a rope and let a ball fall | Shape images, physics, ropes and buttons |
| [Robot Workshop](robot_workshop) | Build an arm, cart and chain | Image shapes, motors and connected parts |
| [Dino Dash](dino_run) | Jump cacti and duck birds | Beginner lessons, scores, restart |
| [Asset Workshop](asset_workshop) | Play with your exported art | Tiled, Pixelorama, two-player controls |
| [Sky Steps](platformer) | Jump and ride a lift | Physics, repeat scripts, a following camera |
| [Beat Blocks](geometry_dash) | Time your jumps | Shape images, glide actions, crash checks |
| [Scrolling World](scrolling_world) | Paint a big world | Tile grids, layers, camera and parallax |
| [Coin Quest](mario) | Collect coins and reach the flag | Lists, physical jumping, scoring |
| [Temple Trail](temple_run) | Jump, slide and turn | Sequences, image changes, perspective |
| [Snake Run](snake_run) | Eat apples and grow | Position history, loops, perspective |
| [Fruit Slice](fruit_ninja) | Swipe fruit, avoid bombs | Random choices, mouse input, geometry |
| [Clone Blaster](clone_blaster) | Fire bullet copies with gamepad B | Clones, sensors, hit handlers and safe removal |
| [Jungle Run](jungle_run) | Run, jump and shoot | Health, bullets, several actions at once |

## Choose your view

Scrolling games use `stage.follow(...)`: characters move through the world while
tiles and obstacles keep their world positions. Arena games use a fixed camera;
Temple Trail and Snake Run use perspective. Scores and controls stay on screen.
Physics stays off unless a game chooses `Stage(physics=True)`.

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
Plocks handles jumps, timed moves and camera following. Your code chooses the
game's rules: where coins go, what a hit does and when you win.
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
