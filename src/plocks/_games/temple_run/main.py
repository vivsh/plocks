"""Temple Trail: a short, original runner using 2D perspective."""

from pathlib import Path

from plocks import (
    Action,
    Anchor,
    Button,
    Ease,
    Event,
    GamepadButton,
    GamepadPress,
    Image,
    Key,
    Label,
    Panel,
    Sprite,
    Stage,
)

# Find assets beside this script, even when running from another folder.
assets = Path(__file__).resolve().parent / "assets"
# Keep the camera fixed. Our perspective code makes distant objects look smaller.
stage = Stage(width=800, height=450, background="#234b43")

# Player one already has Space for jumping; map extra controls here.
player = stage.gamepads[0]
player.map_key(Key.DOWN, GamepadButton.DOWN)
player.map_key(Key.LEFT, GamepadButton.LEFT)
player.map_key(Key.R, GamepadButton.SELECT)
player.map_key(Key.RIGHT, GamepadButton.RIGHT)
# A dictionary lets us choose a picture by its name.
roads = {
    "straight": Image(assets / "road_straight.png"),
    "left": Image(assets / "road_left.png"),
    "right": Image(assets / "road_right.png"),
}
road = Sprite(roads["straight"], layer=-1000)
stage.add(road)
# The anchor is at the feet, so changing pictures keeps the runner on the path.
running = (
    Image(assets / "run1.png", anchor=Anchor.BOTTOM_CENTER),
    Image(assets / "run2.png", anchor=Anchor.BOTTOM_CENTER),
)
jumping = Image(assets / "jump.png", anchor=Anchor.BOTTOM_CENTER)
sliding = Image(assets / "slide.png", anchor=Anchor.BOTTOM_CENTER)
hero = Sprite(running[0], y=-110, scale=1.6, layer=10)
stage.add(hero)
# A sequence is a script: do these steps in order while the rest of the game runs.
jump = hero.sequence()
jump.set_image(jumping)
jump.glide_by(y=85, seconds=0.35, easing=Ease.OUT)
jump.glide_by(y=-85, seconds=0.35, easing=Ease.IN)
jump.set_image(running[0])
slide = hero.sequence()
slide.set_image(sliding)
slide.wait(0.8)
slide.set_image(running[0])

# Each row is (distance along the trail, lane, kind). Hurdles and arches span all lanes.
course = (
    (80, 0, "coin"),
    (125, 0, "coin"),
    (230, 0, "hurdle"),
    (350, -1, "coin"),
    (470, 0, "arch"),
    (680, 0, "left"),
    (800, 0, "coin"),
    (850, 1, "coin"),
    (980, 0, "hurdle"),
    (1110, 0, "coin"),
    (1210, 0, "arch"),
    (1410, 0, "right"),
    (1530, 0, "coin"),
    (1640, 0, "hurdle"),
    (1780, 0, "coin"),
)
images = {
    "coin": Image(assets / "coin.png", anchor=Anchor.BOTTOM_CENTER),
    "hurdle": Image(assets / "hurdle.png", anchor=Anchor.BOTTOM_CENTER),
    "arch": Image(assets / "arch.png", anchor=Anchor.BOTTOM_CENTER),
    "left": Image(assets / "left.png", anchor=Anchor.BOTTOM_CENTER),
    "right": Image(assets / "right.png", anchor=Anchor.BOTTOM_CENTER),
}
# Each live item stores (sprite, distance along the trail, lane, kind).
objects: list[tuple[Sprite, int, int, str]] = []
# Keep the current jump or slide so we can wait for it to finish. None means no action yet.
maneuver: Action | None = None
distance = 0.0
score = 0
heading = 0
outcome = "playing"


hud = Panel(position=(0, 192), width=800, height=66, color="#172e32")
status = Label("TEMPLE TRAIL   Coins 0/8", position=(-380, 0), anchor=Anchor.CENTER_LEFT, size=28)
compass = Label("North", position=(380, 0), anchor=Anchor.CENTER_RIGHT, size=20)
hud.add(status)
hud.add(compass)
stage.add(hud)
turn_hint = Label("", position=(0, 105), size=30, color="#ffe19a")
stage.add(turn_hint)
help_bar = Panel(position=(0, -205), width=800, height=40)
help_bar.add(Label("Left/Right: lanes + turns   Space: jump   Down: slide   R: restart", size=18))
stage.add(help_bar)
result = Panel(width=760, height=150, layer=10)
result_title = Label("Round over!", position=(0, 40), size=25)
again = Button("Play again", position=(0, -25), width=200)
result.add(result_title)
result.add(again)
result.visible = False
stage.add(result)


def next_corner() -> tuple[Sprite, int, int, str] | None:
    """Find the first corner still ahead, or return None if there are no more."""
    for item in objects:
        kind = item[3]
        if kind == "left" or kind == "right":
            return item
    return None


def finish(result: str) -> None:
    global outcome
    outcome = result
    hero.stop()


def reset() -> None:
    global distance, score, heading, outcome, maneuver
    hero.stop()
    hero.position = (0, -110)
    hero.image = running[0]
    maneuver = None
    distance = 0
    score = 0
    heading = 0
    outcome = "playing"
    result.visible = False
    turn_hint.text = ""
    status.text = "TEMPLE TRAIL   Coins 0/8"
    compass.text = "North"
    road.image = roads["straight"]
    stage.background = "#234b43"
    for item in objects:
        actor = item[0]
        stage.remove(actor)
    objects.clear()
    for location, lane, kind in course:
        actor = Sprite(images[kind], visible=False)
        stage.add(actor)
        objects.append((actor, location, lane, kind))


# @ connects the function to a key. A held key does not start another jump.
@hero.on_button_down(GamepadButton.A, gamepad=player)
def start_jump(event: Event[Sprite, GamepadPress]) -> None:
    # global changes the game's action; .done tells us when it has finished.
    global maneuver
    if outcome == "playing" and (maneuver is None or maneuver.done):
        maneuver = hero.act(jump)


@hero.on_button_down(GamepadButton.DOWN, gamepad=player)
def start_slide(event: Event[Sprite, GamepadPress]) -> None:
    # global changes the game's action; .done tells us when it has finished.
    global maneuver
    if outcome == "playing" and (maneuver is None or maneuver.done):
        maneuver = hero.act(slide)


def steer(direction: int) -> None:
    global heading
    if outcome != "playing":
        return
    # A copy lets us safely remove an item from the original list.
    for item in objects.copy():
        actor, location, _, kind = item
        if kind in ("left", "right") and 0 <= location - distance <= 65:
            needed_direction = 1
            if kind == "left":
                needed_direction = -1
            if direction != needed_direction:
                finish("Wrong turn! Follow the arrow.")
                return
            # % wraps the compass around its four headings: North, East, South, West.
            heading = (heading + direction) % 4
            hero.x = 0
            objects.remove(item)
            stage.remove(actor)
            stage.background = ("#234b43", "#30465b", "#514338", "#314e37")[heading]
            return
    hero.x = max(-145, min(145, hero.x + direction * 145))


@hero.on_button_down(GamepadButton.LEFT, gamepad=player)
def left(event: Event[Sprite, GamepadPress]) -> None:
    steer(-1)


@hero.on_button_down(GamepadButton.RIGHT, gamepad=player)
def right(event: Event[Sprite, GamepadPress]) -> None:
    steer(1)


# update runs each game step. dt is its length in seconds; distance is speed × time.
@stage.on_update
def update(event: Event[Stage, float]) -> None:
    dt = event.data
    global distance, score
    if outcome != "playing":
        return
    distance += 110 * dt
    if maneuver is None or maneuver.done:
        # Alternate picture 0 and picture 1 eight times a second.
        frame_number = int(stage.time * 8) % 2
        hero.image = running[frame_number]
    corner = next_corner()
    road.image = roads["straight"]
    if corner is not None:
        corner_distance = corner[1]
        corner_kind = corner[3]
        if corner_distance - distance < 300:
            road.image = roads[corner_kind]
    # A copy lets us safely remove an item from the original list.
    for item in objects.copy():
        actor, location, lane, kind = item
        ahead = location - distance
        # Check an item when it reaches our feet. Hurdles and arches cover all lanes.
        if ahead <= 0:
            if kind == "coin" and abs(hero.x - lane * 145) < 45 and hero.y < -60:
                score += 1
            elif kind == "hurdle" and hero.y < -65:
                finish("Jump over the stones! Space.")
            elif kind == "arch" and hero.image is not sliding:
                finish("Slide under the arch! Down arrow.")
            elif kind in ("left", "right"):
                finish("Missed the corner! Turn when it says NOW.")
            objects.remove(item)
            stage.remove(actor)
            if outcome != "playing":
                break
            continue
        # Faraway items look smaller and nearer the horizon: a simple 3D-looking trick.
        scale = 1 / (1 + ahead / 150)
        actor.visible = ahead < 650
        if corner is not None and location > corner[1]:
            actor.visible = False  # We cannot see around a corner yet.
        actor.scale = scale
        actor.position = (lane * 145 * scale, -110 + 285 * (1 - scale))
        actor.layer = -int(ahead)
    if distance >= 1900 and outcome == "playing":
        finish("Temple reached! Well run.")


@stage.on_update
def show_progress(event: Event[Stage, float]) -> None:
    status.text = f"TEMPLE TRAIL   Coins {score}/8"
    compass.text = ("North", "East", "South", "West")[heading]
    turn_hint.text = ""
    corner = next_corner()
    if outcome == "playing" and corner is not None:
        ahead = corner[1] - distance
        if ahead < 180:
            cue = "NOW!" if ahead <= 65 else "soon..."
            turn_hint.text = f"Turn {corner[3].upper()} {cue}"
    result.visible = outcome != "playing"
    result_title.text = outcome


@again.on_click
def play_again(event: Event[Button, None]) -> None:
    stage.focus(None)
    reset()


@stage.on_button_down(GamepadButton.SELECT, gamepad=player)
def restart(event: Event[Stage, GamepadPress]) -> None:
    reset()


reset()


if __name__ == "__main__":
    stage.run()
