"""Alpine Racer: five minutes of overtaking on a winding, sprite-drawn road."""

from math import ceil, sin, tau
from pathlib import Path

from plocks import (
    Anchor,
    Button,
    Canvas,
    Event,
    GamepadButton,
    GamepadPress,
    Image,
    Key,
    Label,
    Panel,
    Sound,
    Sprite,
    Stage,
    UITheme,
)

# Time is in seconds, speed is in km/h, and lane 0 is the road's middle.
RACE_SECONDS = 300
TOP_SPEED = 360
TRACK_LENGTH = 60000
UNITS_PER_METRE = 30  # Converts real travel distances into our picture coordinates.
CORNER_PUSH = 6  # Higher means stronger outward drift in fast bends.


def road_center(at: float) -> float:
    """Long bends, sharper turns and quick S-bends make a repeatable mountain circuit."""
    angle = tau * at / TRACK_LENGTH
    return 5000 * sin(angle) + 2200 * sin(3 * angle) + 900 * sin(7 * angle)


def map_point(at: float) -> tuple[float, float]:
    """Plot distance within one lap and its real road offset, rotated to fit the route box."""
    scale = 90 / TRACK_LENGTH
    return 360 + at * scale, -173 + road_center(at) * scale


assets = Path(__file__).resolve().parent / "assets"
stage = Stage(
    width=960,
    height=540,
    background="#76b84d",
    ui_theme=UITheme(panel_color="#14263b", accent_color="#ffdf70"),
)
player = stage.gamepads[0]
player.map_key(Key.P, GamepadButton.START)
player.map_key(Key.R, GamepadButton.SELECT)
player.map_key(Key.LEFT, GamepadButton.LEFT)
player.map_key(Key.RIGHT, GamepadButton.RIGHT)
player.map_key(Key.UP, GamepadButton.UP)
player.map_key(Key.DOWN, GamepadButton.DOWN)

# This is perspective, like Temple Trail: the 2D camera stays fixed.
background = Sprite(Image(assets / "valley.png"), y=20, layer=-100)
stage.add(background)
car_images = {
    name: Image(assets / f"car_{name}.png", anchor=Anchor.BOTTOM_CENTER)
    for name in ("straight", "left", "right")
}
car = Sprite(car_images["straight"], y=-225, scale=1.1, layer=1400)
stage.add(car)
bump = Sound(assets / "bump.ogg")

# A road is a stack of thin picture strips. Smaller strips make its distant end.
light_road = Image(assets / "road_light.png")
dark_road = Image(assets / "road_dark.png")
road: list[tuple[Sprite, Image, Image]] = []
for y in range(-270, 75, 5):
    width = max(1, round(1000 * (80 - y) / 350))
    light = light_road.resized(width, 6)
    dark = dark_road.resized(width, 6)
    strip = Sprite(light, y=y, layer=-50)
    stage.add(strip)
    road.append((strip, light, dark))

# Track decorations store (sprite, distance along the circuit, sideways position).
tree_image = Image(assets / "tree.png", anchor=Anchor.BOTTOM_CENTER)
sign_images = {
    direction: Image(assets / f"sign_{direction}.png", anchor=Anchor.BOTTOM_CENTER)
    for direction in ("left", "right")
}
scenery: list[tuple[Sprite, float, float]] = []
for index in range(100):
    for side in (-1, 1):
        tree = Sprite(tree_image, visible=False)
        stage.add(tree)
        scenery.append((tree, index * 600.0, side * 1.35))
    if index % 3 == 0:
        location = index * 600.0 + 120
        turn = road_center(location + 100) - 2 * road_center(location) + road_center(location - 100)
        sign = Sprite(sign_images["right" if turn > 0 else "left"], visible=False)
        stage.add(sign)
        scenery.append((sign, location, 1.08))

# Each rival stores (sprite, lane, distance travelled, cruising speed).
rivals: list[tuple[Sprite, float, float, float]] = []
distance = 0.0
speed = 0.0
lane = 0.0
started_at: float | None = None
bump_until = 0.0


# Screen controls stay in place while the road rushes past.
hud = Panel(position=(0, 231), width=936, height=54)
lap_label = Label("LAP 1", position=(-452, 0), anchor=Anchor.CENTER_LEFT, size=32)
position_label = Label("POSITION 6/6", size=32)
time_label = Label("TIME 05:00", position=(452, 0), anchor=Anchor.CENTER_RIGHT, size=32)
for control in (lap_label, position_label, time_label):
    hud.add(control)
stage.add(hud)
speed_panel = Panel(position=(-468, -152), width=223, height=64, anchor=Anchor.TOP_LEFT)
speed_label = Label("0 km/h", size=38, color="#ffdf70")
speed_panel.add(speed_label)
stage.add(speed_panel)
help_bar = Panel(position=(0, -249), width=960, height=42)
help_bar.add(Label("Arrows / WASD: drive    P: pause    R: restart", size=23))
stage.add(help_bar)
route_panel = Panel(position=(405, -172.5), width=110, height=95)
route_panel.add(Label("ROUTE", position=(0, 33), size=18))
route_panel.add(Label("START     FINISH", position=(0, -35), size=14))
stage.add(route_panel)
menu = Panel(position=(0, 35), width=560, height=170, layer=10)
menu_title = Label("HOLD UP OR W TO RACE", position=(0, 40), size=29, color="#ffdf70")
continue_button = Button("Continue", position=(0, -25), width=200)
continue_button.visible = False
menu.add(menu_title)
menu.add(continue_button)
stage.add(menu)


def time_left() -> float:
    """Use the stage clock, so pause and switching applications freeze race time."""
    return RACE_SECONDS if started_at is None else max(0, RACE_SECONDS - stage.time + started_at)


def project(ahead: float, sideways: float) -> tuple[float, float, float]:
    """Turn distance into a screen position and size; distant things look smaller."""
    scale = 150 / (150 + ahead)
    heading = road_center(distance + 1) - road_center(distance)
    bend = road_center(distance + ahead) - road_center(distance) - heading * ahead
    x = (bend + (sideways - lane) * 500) * scale
    y = 80 - 350 * scale
    return x, y, scale


def place(actor: Sprite, ahead: float, sideways: float) -> None:
    """Show nearby track objects. Larger layer numbers paint nearer objects last."""
    actor.visible = 0 < ahead < 4200
    if actor.visible:
        x, y, size = project(ahead, sideways)
        actor.position = (x, y)
        actor.scale = size
        actor.layer = 200 + round(size * 1000)


def show_road() -> None:
    """Update the pictures from distance; no separate scenery timers are needed."""
    for strip, light, dark in road:
        ahead = 150 / ((80 - strip.y) / 350) - 150
        strip.x = project(ahead, 0)[0]
        strip.image = light if int((distance + ahead) / 180) % 2 else dark
    for actor, location, sideways in scenery:
        place(actor, (location - distance) % TRACK_LENGTH, sideways)
    for actor, sideways, location, _ in rivals:
        place(actor, (location - distance) % TRACK_LENGTH, sideways)
    # Distant mountains shift gently with the road; they do not rush past like trees.
    background.x = -sin(tau * distance / TRACK_LENGTH) * 40


def drive_forward(dt: float) -> None:
    """Advance along the circuit, stopping at any tree trunk in the car's path."""
    global distance, speed, bump_until
    travel = speed / 3.6 * UNITS_PER_METRE * dt
    for actor, location, sideways in scenery:
        # Only trunks block the car: branches can hang over the road safely.
        if actor.image is not tree_image or abs(sideways - lane) >= 0.24:
            continue
        gap = (location - distance) % TRACK_LENGTH
        room = max(0, gap - 65)  # Leave space between the bumper and the trunk.
        # Check the whole journey this frame, so fast cars cannot skip through trees.
        if room < travel:
            travel = room
            speed = 0
            if stage.time >= bump_until:
                bump_until = stage.time + 1
                stage.play(bump, volume=0.3)
    distance += travel


def reset() -> None:
    """Put everyone back at the start, without adding another copy of the course."""
    global distance, speed, lane, started_at, bump_until
    for actor, _, _, _ in rivals:
        stage.remove(actor)
    rivals.clear()
    distance, speed, lane = 0.0, 0.0, 0.0
    started_at, bump_until = None, 0.0
    car.image = car_images["straight"]
    car.visible = True
    for index, cruise in enumerate((280, 305, 330, 346, 354)):
        color = ("blue", "white", "red")[index % 3]
        actor = Sprite(Image(assets / f"bot_{color}.png", anchor=Anchor.BOTTOM_CENTER))
        stage.add(actor)
        rivals.append((actor, (-0.6, 0, 0.6)[index % 3], 250.0 + index * 220, cruise))
    stage.resume()
    show_road()
    refresh_ui()


@stage.on_start
def start(event: Event[Stage, None]) -> None:
    reset()


@stage.on_button_down(GamepadButton.SELECT, gamepad=player)
def restart(event: Event[Stage, GamepadPress]) -> None:
    reset()


@stage.on_button_down(GamepadButton.START, gamepad=player)
def pause(event: Event[Stage, GamepadPress]) -> None:
    if time_left() > 0:
        if stage.paused:
            stage.resume()
        else:
            stage.pause()
        refresh_ui()


@stage.on_update
def update(event: Event[Stage, float]) -> None:
    global speed, lane, started_at, bump_until
    dt = event.data
    steering, pedal = player.left_stick
    # WASD is already mapped. These extra checks let the arrow keys work too.
    if player.is_down(GamepadButton.LEFT):
        steering = -1
    if player.is_down(GamepadButton.RIGHT):
        steering = 1
    accelerating = pedal > 0.2 or player.right_trigger > 0.1 or player.is_down(GamepadButton.A)
    accelerating = accelerating or player.is_down(GamepadButton.UP)
    braking = pedal < -0.2 or player.left_trigger > 0.1 or player.is_down(GamepadButton.B)
    braking = braking or player.is_down(GamepadButton.DOWN)
    if started_at is None:
        if not accelerating:
            return
        started_at = stage.time
    if time_left() <= 0:
        stage.pause()
        refresh_ui()
        return

    # Brakes and grass slow the car; steering changes its lane.
    change = 180 if accelerating else -35
    if braking:
        change = -220
    speed = max(0, min(TOP_SPEED, speed + change * dt))
    # Grass slows us to a crawl, but still lets us accelerate from a standstill.
    if abs(lane) > 0.95 and speed > 90:
        speed = max(90, speed - 420 * dt)
    # Keep a little steering at zero speed so we can always get back onto the road.
    turning = 0.4 + 0.7 * speed / TOP_SPEED
    # Fast corners push us outward. Countersteer, or brake to take them more gently.
    bend = (
        road_center(distance + 300) - 2 * road_center(distance) + road_center(distance - 300)
    ) / 300
    drift = -CORNER_PUSH * bend * (speed / TOP_SPEED) ** 2
    lane = max(-1.6, min(1.6, lane + (steering * turning + drift) * dt))
    drive_forward(dt)
    if steering < -0.15:
        car.image = car_images["left"]
    elif steering > 0.15:
        car.image = car_images["right"]
    else:
        car.image = car_images["straight"]
    car.visible = stage.time >= bump_until or int(stage.time * 12) % 2 == 0

    race_time = stage.time - started_at
    for index, (actor, sideways, location, cruise) in enumerate(rivals):
        location += (cruise + 6 * sin(race_time / 14 + index)) / 3.6 * UNITS_PER_METRE * dt
        ahead = (location - distance) % TRACK_LENGTH
        # Cars occupy a little road space. A bump slows you instead of ending the race.
        if ahead < 65 and abs(sideways - lane) < 0.3 and stage.time >= bump_until:
            speed *= 0.45
            bump_until = stage.time + 1
            stage.play(bump, volume=0.2)
        rivals[index] = (actor, sideways, location, cruise)
    show_road()


def refresh_ui() -> None:
    position = 1 + sum(location > distance for _, _, location, _ in rivals)
    minutes, seconds = divmod(ceil(time_left()), 60)
    lap_label.text = f"LAP {1 + int(distance / TRACK_LENGTH)}"
    position_label.text = f"POSITION {position}/6"
    time_label.text = f"TIME {minutes:02}:{seconds:02}"
    speed_label.text = f"{int(speed)} km/h"
    menu.visible = started_at is None or stage.paused
    menu_title.text = "HOLD UP OR W TO RACE" if started_at is None else "PAUSED"
    if time_left() == 0:
        menu_title.text = f"FINISHED {position}/6"
    continue_button.visible = started_at is not None
    continue_button.text = "Race again" if time_left() == 0 else "Continue"


@stage.on_update
def show_race_info(event: Event[Stage, float]) -> None:
    refresh_ui()


@continue_button.on_click
def continue_race(event: Event[Button, None]) -> None:
    stage.focus(None)
    if time_left() == 0:
        reset()
    else:
        stage.resume()
        refresh_ui()


@stage.on_draw
def draw(canvas: Canvas) -> None:
    # The route is the actual road offset against distance, not an invented oval.
    # It repeats each lap; the start is on the left and the finish is on the right.
    for index in range(128):
        canvas.line(
            map_point(TRACK_LENGTH * index / 128),
            map_point(TRACK_LENGTH * (index + 1) / 128),
            color="#a2b2b9",
            width=2,
        )
    for _, _, location, _ in rivals:
        canvas.circle(map_point(location % TRACK_LENGTH), 2, color="#72c4ff")
    canvas.circle(map_point(distance % TRACK_LENGTH), 3, color="#ffac43")


if __name__ == "__main__":
    stage.run()
