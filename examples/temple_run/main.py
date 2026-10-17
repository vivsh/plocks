"""Temple Trail: a short, original runner using 2D perspective."""

from pathlib import Path

from plocks import Action, Bounds, Canvas, Costume, Ease, Key, Sprite, Stage

# Find the pictures beside main.py, even if you run it from another folder.
assets = Path(__file__).resolve().with_name("assets")
stage = Stage(width=800, height=450, background="#234b43")
# A dictionary lets us choose a picture by its name.
roads = {
    "straight": Costume(assets / "road_straight.png"),
    "left": Costume(assets / "road_left.png"),
    "right": Costume(assets / "road_right.png"),
}
road = Sprite(roads["straight"], layer=-1000)
stage.add(road)
# The anchor is at the feet, so changing pictures keeps the runner on the path.
running = (
    Costume(assets / "run1.png", anchor=(18, 48)),
    Costume(assets / "run2.png", anchor=(18, 48)),
)
jumping = Costume(assets / "jump.png", anchor=(18, 48))
sliding = Costume(assets / "slide.png", anchor=(30, 28))
hero = Sprite(running[0], y=-110, scale=1.6, layer=10)
stage.add(hero)
# A sequence is a recipe: do these steps in order while the rest of the game runs.
jump = hero.sequence()
jump.set_costume(jumping)
jump.glide_by(y=85, seconds=0.35, easing=Ease.OUT)
jump.glide_by(y=-85, seconds=0.35, easing=Ease.IN)
jump.set_costume(running[0])
slide = hero.sequence()
slide.set_costume(sliding)
slide.wait(0.8)
slide.set_costume(running[0])

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
costumes = {
    "coin": Costume(assets / "coin.png", anchor=(10, 24)),
    "hurdle": Costume(assets / "hurdle.png", anchor=(230, 40)),
    "arch": Costume(assets / "arch.png", anchor=(240, 105)),
    "left": Costume(assets / "left.png", anchor=(65, 96)),
    "right": Costume(assets / "right.png", anchor=(65, 96)),
}
# Each live item stores (sprite, distance along the trail, lane, kind).
objects: list[tuple[Sprite, int, int, str]] = []
# Keep the current jump or slide so we can wait for it to finish. None means no action yet.
maneuver: Action | None = None
distance = 0.0
score = 0
heading = 0
outcome = "playing"


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


@stage.on_key_down(Key.R)
def reset() -> None:
    global distance, score, heading, outcome, maneuver
    hero.stop()
    hero.position = (0, -110)
    hero.costume = running[0]
    maneuver = None
    distance = 0
    score = 0
    heading = 0
    outcome = "playing"
    road.costume = roads["straight"]
    stage.background = "#234b43"
    for item in objects:
        actor = item[0]
        stage.remove(actor)
    objects.clear()
    for location, lane, kind in course:
        actor = Sprite(costumes[kind], visible=False)
        stage.add(actor)
        objects.append((actor, location, lane, kind))


# @ connects the function to a key. A held key does not start another jump.
@hero.on_key_down(Key.SPACE)
def start_jump() -> None:
    # global changes the game's action; .done tells us when it has finished.
    global maneuver
    if outcome == "playing" and (maneuver is None or maneuver.done):
        maneuver = hero.act(jump)


@hero.on_key_down(Key.DOWN)
def start_slide() -> None:
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


@hero.on_key_down(Key.LEFT)
def left() -> None:
    steer(-1)


@hero.on_key_down(Key.RIGHT)
def right() -> None:
    steer(1)


# update runs each game step. dt is its length in seconds; distance is speed × time.
@stage.on_update
def update(dt: float) -> None:
    global distance, score
    if outcome != "playing":
        return
    distance += 110 * dt
    if maneuver is None or maneuver.done:
        # Alternate picture 0 and picture 1 eight times a second.
        frame_number = int(stage.time * 8) % 2
        hero.costume = running[frame_number]
    corner = next_corner()
    road.costume = roads["straight"]
    if corner is not None:
        corner_distance = corner[1]
        corner_kind = corner[3]
        if corner_distance - distance < 300:
            road.costume = roads[corner_kind]
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
            elif kind == "arch" and hero.costume is not sliding:
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


@stage.on_draw
def draw(canvas: Canvas) -> None:
    canvas.text(f"TEMPLE TRAIL   Coins {score}/8", (-380, 207), size=28)
    canvas.text(f"Heading: {('North', 'East', 'South', 'West')[heading]}", (185, 205), size=20)
    canvas.text(
        "Left/Right: lanes + turns   Space: jump   Down: slide   R: restart",
        (-380, -202),
        size=18,
    )
    corner = next_corner()
    if outcome == "playing" and corner is not None:
        corner_distance = corner[1]
        corner_kind = corner[3]
        if corner_distance - distance < 180:
            cue = "soon..."
            if corner_distance - distance <= 65:
                cue = "NOW!"
            canvas.text(f"Turn {corner_kind.upper()} {cue}", (-150, 105), size=30, color="#ffe19a")
    if outcome != "playing":
        canvas.rectangle(Bounds(-360, 0, 360, 90), color="#172e32")
        canvas.text(outcome, (-340, 65), size=25)
        canvas.text("Press R to run again", (-150, 25), size=22, color="#ffe19a")


reset()


if __name__ == "__main__":
    stage.run()
