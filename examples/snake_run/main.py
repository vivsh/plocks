"""Snake Run: a 2D game with perspective, not a 3D engine."""

from pathlib import Path

from plocks import Canvas, Key, Sprite, Stage

# Load the ready-made pictures from the folder beside this script.
assets = Path(__file__).resolve().with_name("assets")
stage = Stage(width=800, height=450, background="#172d46")
stage.add(Sprite(assets / "track.png", layer=-1000))
head = Sprite(assets / "snake_head.png", y=-100, scale=1.2, layer=100)
stage.add(head)
# Lists remember the body pieces, earlier head positions and things on the track.
segments: list[Sprite] = []
history: list[float] = []
# Each track item stores (sprite, lane, distance along the track, kind).
objects: list[tuple[Sprite, int, float, str]] = []
distance = 0.0
score = 0
outcome = "playing"


def grow() -> None:
    """Add a body piece, up to ten, so the snake still fits on screen."""
    if len(segments) < 10:
        segment = Sprite(assets / "snake_body.png", layer=90 - len(segments))
        stage.add(segment)
        segments.append(segment)


@stage.on_key_down(Key.R)
def reset() -> None:
    """Clear the old game and build a fresh track."""
    global distance, score, outcome
    for segment in segments:
        stage.remove(segment)
    for item in objects:
        actor = item[0]
        stage.remove(actor)
    segments.clear()
    objects.clear()
    history.clear()
    history.extend([0.0] * 64)
    head.x = 0
    distance = 0
    score = 0
    outcome = "playing"
    for _ in range(3):
        grow()
    # lane -1 is left, 0 is the middle, 1 is right; distance is down the track.
    for index, lane in enumerate((0, -1, 1, 0, 1, -1, 0, 1, -1, 0, 0, -1, 1, 0, -1, 1)):
        # % finds the remainder. Here it makes every third item a rock.
        kind = "apple"
        if index % 3 == 2:
            kind = "rock"
        actor = Sprite(assets / f"{kind}.png", visible=False)
        stage.add(actor)
        objects.append((actor, lane, 160.0 + index * 95, kind))


# @ asks Plocks to call this function every game step; dt is the step time.
@stage.on_update
def update(dt: float) -> None:
    # global lets this helper update the game's score and progress.
    global distance, score, outcome
    if outcome != "playing":
        return
    direction = 0
    if stage.keyboard.is_down(Key.RIGHT):
        direction += 1
    if stage.keyboard.is_down(Key.LEFT):
        direction -= 1
    head.x = max(-185, min(185, head.x + direction * 280 * dt))
    history.append(head.x)
    # Keep only the latest 64 positions; old ones are no longer needed.
    if len(history) > 64:
        history.pop(0)
    for index, segment in enumerate(segments):
        # Each piece follows an older head position, making the tail bend.
        steps_behind = (index + 1) * 5
        old_x = history[-steps_behind]
        segment.position = (old_x, -120 - index * 10)
        segment.scale = 1.1 + index * 0.025
    distance += 110 * dt
    # Use a copy because we remove items after passing them.
    for item in objects.copy():
        actor, lane, location, kind = item
        ahead = location - distance
        if ahead < 0:
            if abs(head.x - lane * 145) < 42:
                if kind == "apple":
                    score += 1
                    grow()
                else:
                    for _ in range(min(2, len(segments))):
                        stage.remove(segments.pop())
                    if not segments:
                        outcome = "Snake stopped!"
            objects.remove(item)
            stage.remove(actor)
            continue
        # Faraway things look small and high on the screen.
        # As ahead approaches zero, scale approaches 1: the item reaches us.
        scale = 1 / (1 + ahead / 150)
        actor.visible = ahead < 650
        actor.scale = scale * 1.3
        actor.position = (lane * 145 * scale, -100 + 290 * (1 - scale))
        actor.layer = -int(ahead)
    if distance >= 1750 and outcome == "playing":
        outcome = "Finish line!"


# Drawing shows our changing score without changing the game itself.
@stage.on_draw
def draw(canvas: Canvas) -> None:
    canvas.text(f"SNAKE RUN    Apples {score}    Length {len(segments) + 1}", (-380, 207), size=27)
    canvas.text("Arrows: steer   Apples: grow   Rocks: shrink   R: restart", (-380, -202), size=19)
    if outcome != "playing":
        canvas.text(outcome + " Press R.", (-220, 65), size=30, color="#ffe29b")


reset()


if __name__ == "__main__":
    stage.run()
