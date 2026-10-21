"""Fruit Slice: hold the mouse button and swipe through tossed fruit."""

from pathlib import Path
from random import choice, uniform

from plocks import (
    Canvas,
    Event,
    GamepadButton,
    GamepadPress,
    Image,
    Key,
    MouseButton,
    Point,
    Sound,
    Sprite,
    Stage,
)


def crosses(start: Point, end: Point, center: Point, radius: float) -> bool:
    """Does the swipe pass close enough to the fruit to cut it?"""
    # This helper contains the trickier maths. You can use it as a yes/no question.
    # Check the whole swipe, so a fast mouse movement cannot jump over a fruit.
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return False
    # Find the closest point on the swipe. A fraction of 0 is the start; 1 is the end.
    toward_fruit_x = center[0] - start[0]
    toward_fruit_y = center[1] - start[1]
    fraction = (toward_fruit_x * dx + toward_fruit_y * dy) / length_squared
    fraction = max(0, min(1, fraction))
    closest_x = start[0] + fraction * dx
    closest_y = start[1] + fraction * dy
    distance_squared = (closest_x - center[0]) ** 2 + (closest_y - center[1]) ** 2
    return distance_squared <= radius**2


# Find assets beside this script, even when running from another folder.
assets = Path(__file__).resolve().parent / "assets"
# Keep the camera fixed: fruit and mouse positions share the same coordinates.
stage = Stage(width=800, height=450, background="#192b40")

# Add this game's controls to player one.
player = stage.gamepads[0]
player.map_key(Key.R, GamepadButton.SELECT)
names = ("apple", "orange", "melon", "bomb")
# Dictionaries let us look up the whole fruit and its two cut pieces by name.
images: dict[str, Image] = {}
halves: dict[str, tuple[Image, Image]] = {}
for name in names:
    images[name] = Image(assets / f"{name}.png")
    if name != "bomb":
        left_half = Image(assets / f"{name}_left.png")
        right_half = Image(assets / f"{name}_right.png")
        halves[name] = (left_half, right_half)
pop = Sound(assets / "pop.ogg")
# Each flying item stores (sprite, sideways speed, upward speed, spin, kind).
# The same list holds whole fruit, bombs and cut pieces.
flying: list[tuple[Sprite, float, float, float, str]] = []
trail: list[Point] = []
previous: Point | None = None
next_throw = 0.0
thrown = 0
score = 0
missed = 0
over = False


def throw() -> None:
    """Toss one fruit upward; every fifth toss is a bomb."""
    global thrown
    thrown += 1
    # % gives the remainder after division. A remainder of zero means "every fifth".
    if thrown % 5 == 0:
        name = "bomb"
    else:
        name = choice(("apple", "orange", "melon"))
    fruit = Sprite(images[name], x=uniform(-260, 260), y=-260, scale=1.4)
    stage.add(fruit)
    speed_x = -fruit.x * 0.25  # Aim gently toward the middle.
    speed_y = uniform(650, 750)
    spin = uniform(-140, 140)
    flying.append((fruit, speed_x, speed_y, spin, name))


@stage.on_button_down(GamepadButton.SELECT, gamepad=player)
def restart(event: Event[Stage, GamepadPress]) -> None:
    global score, missed, over, thrown, next_throw, previous
    for item in flying:
        fruit = item[0]
        stage.remove(fruit)
    flying.clear()
    trail.clear()
    score = 0
    missed = 0
    over = False
    thrown = 0
    next_throw = stage.time
    previous = None


# @ asks Plocks to run update every game step. dt is that step's time in seconds.
@stage.on_update
def update(event: Event[Stage, float]) -> None:
    # These are the game variables at the top of this file, not new variables inside update.
    dt = event.data
    global previous, next_throw, score, missed, over
    if over:
        previous = None
        trail.clear()
        return
    if stage.time >= next_throw:
        throw()
        next_throw = stage.time + 0.8
    pointer = stage.mouse.position
    cutting = stage.mouse.is_down(MouseButton.LEFT)
    # Join the last mouse position to this one to make a swipe.
    start = None
    if cutting:
        start = previous
        previous = pointer
        trail.append(pointer)
        if len(trail) > 8:
            trail.pop(0)
    else:
        previous = None
        trail.clear()
    sliced = 0
    # A copy lets us safely remove sliced fruit and add its halves.
    for item in flying.copy():
        fruit, speed_x, speed_y, spin, name = item
        fruit.x += speed_x * dt
        fruit.y += speed_y * dt
        fruit.direction += spin * dt
        flying.remove(item)
        if fruit.y < -300 and speed_y < 0:
            stage.remove(fruit)
            if name not in ("bomb", "half"):
                missed += 1
                if missed >= 3:
                    over = True
            continue
        if name != "half" and start is not None and crosses(start, pointer, fruit.position, 30):
            stage.remove(fruit)
            if name == "bomb":
                over = True
                continue
            score += 1
            sliced += 1
            # Pair each half with its direction: -1 flies left, +1 flies right.
            for direction, image in zip((-1, 1), halves[name]):
                half = Sprite(image, x=fruit.x, y=fruit.y, scale=1.4)
                stage.add(half)
                flying.append(
                    (half, speed_x + direction * 120, speed_y + 80, direction * 230, "half")
                )
        else:
            # Gravity slows the rise, then pulls the fruit down.
            flying.append((fruit, speed_x, speed_y - 1000 * dt, spin, name))
    if sliced:
        # Cutting several fruit in one step earns a bonus.
        if sliced > 1:
            score += sliced - 1
        stage.play(pop, volume=0.25)


@stage.on_draw
def draw(canvas: Canvas) -> None:
    # Connect neighbouring mouse positions to show a short glowing trail.
    for index in range(1, len(trail)):
        canvas.line(trail[index - 1], trail[index], color="#d2fcff", width=4)
    canvas.text(f"FRUIT SLICE    Score {score}    Missed {missed}/3", (-380, 207), size=27)
    canvas.text("Hold left mouse + swipe. Avoid bombs! R: restart", (-380, -198), size=20)
    if over:
        canvas.text("Round over! Press R to try again.", (-240, 20), size=30, color="#ffd07a")


if __name__ == "__main__":
    stage.run()
