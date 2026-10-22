"""Beat Blocks: a short auto-running jump course."""

from pathlib import Path

from plocks import (
    Action,
    Anchor,
    Bounds,
    Button,
    Ease,
    Event,
    GamepadButton,
    GamepadPress,
    Image,
    Key,
    Label,
    Panel,
    ProgressBar,
    Sound,
    Sprite,
    Stage,
    TileMap,
)

# Find assets beside this script, even when running from another folder.
assets = Path(__file__).resolve().parent / "assets"
stage = Stage(width=800, height=450, background="#19253d")

# Player one already has Space for jumping; map extra controls here.
player = stage.gamepads[0]
player.map_key(Key.R, GamepadButton.SELECT)
# Repeat a stone tile to make the floor. layer=-1 puts it behind the hero.
ground = TileMap(
    ["#" * 100] * 2,
    {"#": assets / "stone.png"},
    tile_size=(32, 32),
    solid={"#"},
    x=-400,
    y=-140,
    layer=-1,
)
stage.add(ground)
hero = Sprite(
    Image.rectangle(32, 32, color="#ffe16a", outline="#fff0b0", outline_width=3), x=-240, y=-124
)
stage.add(hero)
# Follow the cube through the world. One-screen-high bounds keep jumps from moving the view up.
stage.follow(
    hero, offset=(120, 0), bounds=Bounds(ground.bounds.left, -225, ground.bounds.right, 225)
)
spikes: list[Sprite] = []
# Change these x positions to design your own obstacle course.
for x in (40, 280, 520, 552, 840, 1100, 1132, 1420, 1680, 1712, 2000):
    spike = Sprite(Image.triangle(32, 32, color="#f06499", outline="#ffb0cf"), x=x, y=-124)
    stage.add(spike)
    spikes.append(spike)
pop = Sound(assets / "pop.ogg")
outcome = "playing"
attempts = 1


# A progress bar fills as we travel. The panel keeps our score together.
hud = Panel(position=(0, 185), width=800, height=80)
status = Label("BEAT BLOCKS    Attempt 1", position=(-380, 18), anchor=Anchor.CENTER_LEFT)
progress = ProgressBar(position=(-380, -16), width=760, height=10, anchor=Anchor.CENTER_LEFT)
hud.add(status)
hud.add(progress)
stage.add(hud)
help_bar = Panel(position=(0, -205), width=800, height=40)
help_bar.add(Label("Space: jump   R: restart    Time your jumps!", size=18))
stage.add(help_bar)
result = Panel(width=520, height=150, layer=10)
result_title = Label("Round over!", position=(0, 40), size=28)
again = Button("Play again", position=(0, -25), width=200)
result.add(result_title)
result.add(again)
result.visible = False
stage.add(result)


# @ connects this function to Space. Only jump when the cube is on the floor.
@hero.on_button_down(GamepadButton.A, gamepad=player)
def jump(event: Event[Sprite, GamepadPress]) -> Action | None:
    if outcome != "playing" or hero.y != -124:
        return None
    # after joins the two halves. Returning the action keeps this jump busy.
    up = hero.glide_by(y=100, seconds=0.35, easing=Ease.OUT)
    return hero.glide_by(y=-100, seconds=0.35, easing=Ease.IN, after=up)


def reset() -> None:
    global outcome, attempts
    hero.stop()
    hero.position = (-240, -124)
    hero.direction = 90
    outcome = "playing"
    attempts += 1
    result.visible = False
    status.text = f"BEAT BLOCKS    Attempt {attempts}"
    progress.value = 0


@stage.on_button_down(GamepadButton.SELECT, gamepad=player)
def restart(event: Event[Stage, GamepadPress]) -> None:
    reset()


@again.on_click
def play_again(event: Event[Button, None]) -> None:
    stage.focus(None)
    reset()


# Plocks runs update each game step. dt is that step's length in seconds.
@stage.on_update
def update(event: Event[Stage, float]) -> None:
    dt = event.data
    global outcome
    if outcome != "playing":
        return
    # Speed × time tells us how far to move. The cube runs without a held key.
    hero.x += 230 * dt
    if hero.y == -124:
        hero.direction = 90
    else:
        hero.direction += 360 * dt
    # A hitbox is an invisible box used to test a crash.
    # These boxes are a little smaller than the pictures, to make near misses fair.
    body = Bounds(hero.x - 12, hero.y - 12, hero.x + 12, hero.y + 12)
    for spike in spikes:
        danger = Bounds(spike.x - 8, -140, spike.x + 8, -116)
        if body.intersects(danger):
            outcome = "Crash!"
            hero.stop()
            stage.play(pop, volume=0.2)
            break
    if hero.x >= 2200:
        outcome = "Course complete!"
        hero.stop()


# Updating a label changes its words; Plocks handles the drawing.
@stage.on_update
def show_progress(event: Event[Stage, float]) -> None:
    progress.value = max(0, min(100, (hero.x + 240) / 2440 * 100))
    status.text = f"BEAT BLOCKS    {int(progress.value)}%    Attempt {attempts}"
    result.visible = outcome != "playing"
    result_title.text = outcome


if __name__ == "__main__":
    stage.run()
