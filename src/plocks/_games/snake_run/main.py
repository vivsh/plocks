"""Snake Run: a 2D game with perspective, not a 3D engine."""

from pathlib import Path

from plocks import (
    Button,
    Event,
    GamepadButton,
    GamepadPress,
    Key,
    Label,
    Panel,
    Sprite,
    Stage,
)

# Find assets beside this script, even when running from another folder.
assets = Path(__file__).resolve().parent / "assets"
# Keep the camera fixed. We draw distance by making faraway objects smaller.
stage = Stage(width=800, height=450, background="#172d46")

# Add this game's controls to player one.
player = stage.gamepads[0]
player.map_left_stick(left=Key.LEFT, right=Key.RIGHT)
player.map_key(Key.R, GamepadButton.SELECT)
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


hud = Panel(position=(0, 195), width=800, height=60)
status = Label("SNAKE RUN    Apples 0    Length 4", size=27)
hud.add(status)
stage.add(hud)
help_bar = Panel(position=(0, -205), width=800, height=40)
help_bar.add(Label("Arrows: steer   Apples: grow   Rocks: shrink   R: restart", size=18))
stage.add(help_bar)
result = Panel(width=520, height=150, layer=10)
result_title = Label("Round over!", position=(0, 40), size=28)
again = Button("Play again", position=(0, -25), width=200)
result.add(result_title)
result.add(again)
result.visible = False
stage.add(result)


def grow() -> None:
    """Add a body piece, up to ten, so the snake still fits on screen."""
    if len(segments) < 10:
        segment = Sprite(assets / "snake_body.png", layer=90 - len(segments))
        stage.add(segment)
        segments.append(segment)


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
    result.visible = False
    status.text = "SNAKE RUN    Apples 0    Length 4"
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
def update(event: Event[Stage, float]) -> None:
    # global lets this helper update the game's score and progress.
    dt = event.data
    global distance, score, outcome
    if outcome != "playing":
        return
    direction = player.left_stick[0]
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


# A label shows our changing score without a drawing callback.
@stage.on_update
def show_score(event: Event[Stage, float]) -> None:
    status.text = f"SNAKE RUN    Apples {score}    Length {len(segments) + 1}"
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
