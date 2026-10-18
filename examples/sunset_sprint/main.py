"""Sunset Sprint: steer one car freely against three computer racers."""

from math import atan2, cos, degrees, hypot, radians, sin, tau
from pathlib import Path

from plocks import Bounds, Canvas, Costume, Event, Key, Sound, Sprite, Stage

# Find assets beside this script, even when running from another folder.
assets = Path(__file__).resolve().parent / "assets"
stage = Stage(width=800, height=450, background="#271c35")
track = Sprite(Costume(assets / "track.png").resized(width=800, height=450), layer=-10)
stage.add(track)

# The player is teal. Ruby, lime and violet are computer racers.
player = Sprite(Costume(assets / "teal_car.png").resized(width=48, height=48), layer=3)
stage.add(player)
bot_costumes = {
    "Ruby": Costume(assets / "ruby_car.png").resized(width=48, height=48),
    "Lime": Costume(assets / "lime_car.png").resized(width=48, height=48),
    "Violet": Costume(assets / "violet_car.png").resized(width=48, height=48),
}
# A bot stores: picture, lap progress, lane, speed, and its display name.
bots: list[tuple[Sprite, float, float, float, str]] = []
for costume, progress, lane, bot_speed, name in (
    (bot_costumes["Ruby"], -0.14, -0.45, 0.185, "Ruby"),
    (bot_costumes["Lime"], -0.21, 0.0, 0.176, "Lime"),
    (bot_costumes["Violet"], -0.28, 0.45, 0.181, "Violet"),
):
    bot = Sprite(costume, layer=2)
    stage.add(bot)
    bots.append((bot, progress, lane, bot_speed, name))

race_theme = Sound(assets / "race_theme.ogg")
engine_sound = Sound(assets / "engine.ogg")
bump_sound = Sound(assets / "bump.ogg")

# The player has a real position, heading and speed. Progress is only for laps/ranking.
start_angle = -0.25 * tau
player_progress = 0.0
start_heading = 90.0
player_heading = start_heading
speed = 0.0
bump_until = 0.0
outcome = "Race to 3 laps!"


def track_point(progress: float, lane: float = 0.0) -> tuple[float, float]:
    """Return one point on a bot's racing line around the oval."""
    angle = start_angle + progress * tau
    return (275 + lane * 22) * cos(angle), (125 + lane * 12) * sin(angle)


def place_bot(car: Sprite, progress: float, lane: float) -> None:
    """Put a bot on its line and face it along the curve."""
    angle = start_angle + progress * tau
    radius_x = 275 + lane * 22
    radius_y = 125 + lane * 12
    car.position = radius_x * cos(angle), radius_y * sin(angle)
    moving_direction = degrees(atan2(-radius_x * sin(angle), radius_y * cos(angle)))
    # Car pictures point up, while an unrotated Plocks costume has direction 90.
    car.direction = moving_direction + 90


def road_zone(position: tuple[float, float]) -> str:
    """Classify a point as road, infield grass, or the outer wall."""
    x, y = position
    outer = (x / 345) ** 2 + (y / 165) ** 2
    inner = (x / 210) ** 2 + (y / 90) ** 2
    if outer > 1.05:
        return "wall"
    if inner < 1.0:
        return "grass"
    return "road"


def update_player_progress(previous: tuple[float, float]) -> None:
    """Add the small signed turn around the circuit to the player's lap progress."""
    global player_progress
    before = atan2(previous[1] / 125, previous[0] / 275)
    after = atan2(player.y / 125, player.x / 275)
    change = (after - before + 0.5 * tau) % tau - 0.5 * tau
    player_progress += change / tau


def place_player_at_start() -> None:
    """Put the player on the starting straight, facing towards the first corner."""
    player.position = track_point(0)
    player.direction = player_heading + 90


def ranking() -> int:
    """Return the player's current race position among the four cars."""
    return 1 + sum(progress > player_progress for _, progress, _, _, _ in bots)


@stage.on_start
def start_music(event: Event[Stage, None]) -> None:
    # Music begins when the stage starts.
    stage.play(race_theme, volume=0.2, loop=True)


@stage.on_key_down(Key.W)
@stage.on_key_down(Key.UP)
def rev_engine(event: Event[Stage, Key]) -> None:
    if outcome == "Race to 3 laps!":
        stage.play(engine_sound, volume=0.25)


@stage.on_key_down(Key.SPACE)
def boost(event: Event[Stage, Key]) -> None:
    """Give a small burst without taking control away from the player."""
    global speed
    if outcome == "Race to 3 laps!":
        speed = min(355.0, speed + 95.0)
        stage.play(engine_sound, volume=0.35)


@stage.on_key_down(Key.R)
def restart(event: Event[Stage, Key]) -> None:
    global bump_until, outcome, player_heading, player_progress, speed
    player_progress = 0.0
    player_heading = start_heading
    speed = 0.0
    bump_until = 0.0
    outcome = "Race to 3 laps!"
    starts = (-0.14, -0.21, -0.28)
    rebuilt: list[tuple[Sprite, float, float, float, str]] = []
    for item, progress in zip(bots, starts):
        car, _, lane, bot_speed, name = item
        rebuilt.append((car, progress, lane, bot_speed, name))
    bots[:] = rebuilt
    place_player_at_start()


def drive(dt: float) -> None:
    """Read held keys, turn freely, and keep the player inside the circuit walls."""
    global bump_until, player_heading, speed
    if stage.keyboard.is_down(Key.W) or stage.keyboard.is_down(Key.UP):
        speed = min(330.0, speed + 260.0 * dt)
    elif stage.keyboard.is_down(Key.S) or stage.keyboard.is_down(Key.DOWN):
        speed = max(-105.0, speed - 410.0 * dt)
    elif speed > 0:
        speed = max(0.0, speed - 75.0 * dt)
    else:
        speed = min(0.0, speed + 100.0 * dt)

    turn = 155 * dt * max(0.25, min(1, abs(speed) / 120))
    if stage.keyboard.is_down(Key.A) or stage.keyboard.is_down(Key.LEFT):
        player_heading -= turn if speed >= 0 else -turn
    if stage.keyboard.is_down(Key.D) or stage.keyboard.is_down(Key.RIGHT):
        player_heading += turn if speed >= 0 else -turn
    player.direction = player_heading + 90

    previous = player.position
    angle = radians(player_heading)
    player.position = (
        player.x + sin(angle) * speed * dt,
        player.y + cos(angle) * speed * dt,
    )
    zone = road_zone(player.position)
    if zone == "wall":
        # The painted kerb is a wall: bounce back rather than silently steering for the child.
        player.position = previous
        speed = -speed * 0.22
        if stage.time >= bump_until:
            stage.play(bump_sound, volume=0.35)
            bump_until = stage.time + 0.25
    elif zone == "grass":
        # Grass and gravel are driveable but slow. The player can choose the risky shortcut.
        speed *= 0.965
    update_player_progress(previous)


def move_bots(dt: float) -> None:
    """Advance each opponent on a slightly shifting racing line."""
    global outcome
    updated: list[tuple[Sprite, float, float, float, str]] = []
    for car, progress, lane, bot_speed, name in bots:
        progress += bot_speed * dt
        live_lane = lane + sin(stage.time * 0.8 + progress * tau) * 0.07
        place_bot(car, progress, live_lane)
        updated.append((car, progress, lane, bot_speed, name))
        if progress >= 3:
            outcome = f"{name} wins! Press R to race again."
    bots[:] = updated


def collide_with_bots() -> None:
    """Make a side-by-side clash cost speed and move the player away from the bot."""
    global bump_until, speed
    if stage.time < bump_until:
        return
    for car, _, _, _, _ in bots:
        if player.touching(car):
            away_x = player.x - car.x
            away_y = player.y - car.y
            distance = max(1, hypot(away_x, away_y))
            player.position = player.x + away_x / distance * 10, player.y + away_y / distance * 10
            speed = -speed * 0.28
            bump_until = stage.time + 0.45
            stage.play(bump_sound, volume=0.4)
            return


# update runs many times each second. Hold keys to drive smoothly and freely.
@stage.on_update
def update(event: Event[Stage, float]) -> None:
    dt = event.data
    global outcome
    if outcome != "Race to 3 laps!":
        return
    drive(dt)
    move_bots(dt)
    collide_with_bots()
    if player_progress >= 3:
        outcome = "You win Sunset Sprint! Press R to race again."


# Canvas drawings stay above the beautiful track, cars, and sunset.
@stage.on_draw
def draw(canvas: Canvas) -> None:
    canvas.rectangle(Bounds(-392, 176, 392, 214), color="#1e2438")
    canvas.text("SUNSET SPRINT", (-385, 187), size=25, color="#fff0b6")
    canvas.text(f"LAP {min(3, max(1, int(player_progress) + 1))}/3", (-30, 187), size=23)
    canvas.text(f"POSITION {ranking()}/4", (135, 187), size=23, color="#a9fff1")
    canvas.rectangle(Bounds(-392, 140, 392, 170), color="#1e2438")
    canvas.text(f"SPEED {int(abs(speed))}", (-385, 148), size=20, color="#fff4cf")
    canvas.text(outcome, (-125, 148), size=20, color="#fff4cf")
    canvas.text(
        "WASD or arrows: drive   SPACE: boost   R: restart",
        (-375, -207),
        size=18,
    )


# Place every car once before the first frame is drawn.
place_player_at_start()
for car, progress, lane, _bot_speed, _name in bots:
    place_bot(car, progress, lane)


if __name__ == "__main__":
    stage.run()
