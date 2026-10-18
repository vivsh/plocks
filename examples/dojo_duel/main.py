"""Dojo Duel: a short two-player martial-arts match."""

from pathlib import Path

from plocks import (
    Action,
    Bounds,
    Canvas,
    Costume,
    Event,
    Key,
    Message,
    Script,
    Sound,
    Sprite,
    SpriteSheet,
    Stage,
)

# Find assets beside this script, even when running from another folder.
assets = Path(__file__).resolve().parent / "assets"
stage = Stage(width=800, height=450, background="#11192c")

# A background sprite lets a large painted picture fill the whole stage.
arena = Sprite(Costume(assets / "dojo.png").resized(width=800, height=450), layer=-10)
stage.add(arena)

# Each sheet holds three pictures: standing, punching, and kicking.
teal_sheet = SpriteSheet(assets / "teal_fighter_sheet.png", frame_size=(724, 724))
ruby_sheet = SpriteSheet(assets / "ruby_fighter_sheet.png", frame_size=(724, 724))
teal_frames = tuple(
    teal_sheet.frame(row=0, column=column, anchor=(362, 710)) for column in range(3)
)
ruby_frames = tuple(
    ruby_sheet.frame(row=0, column=column, anchor=(362, 710)).flipped(horizontal=True)
    for column in range(3)
)

# The blue fighter looks right; the ruby fighter's prepared costumes look left.
blue = Sprite(teal_frames[0], x=-190, y=-140, scale=0.48, layer=2)
ruby = Sprite(ruby_frames[0], x=190, y=-140, scale=0.48, layer=2)
stage.add(blue)
stage.add(ruby)
hit_sound = Sound(assets / "hit.ogg")
dojo_theme = Sound(assets / "dojo_theme.ogg")
punch_sound = Sound(assets / "punch.ogg")
kick_sound = Sound(assets / "kick.ogg")

# These variables remember the game while it is running.
blue_health = 100
ruby_health = 100
blue_speed_y = 0.0
ruby_speed_y = 0.0
blue_attack: Action | None = None
ruby_attack: Action | None = None
impact: tuple[float, float, float] | None = None
outcome = "Round 1"
ground_y = -140


def ready(action: Action | None) -> bool:
    """Return True when a fighter has no punch or kick in progress."""
    return action is None or action.done


def close_enough(attacker: Sprite, defender: Sprite, reach: float) -> bool:
    """An attack connects only when both fighters are near the same height."""
    return abs(attacker.x - defender.x) <= reach and abs(attacker.y - defender.y) < 85


def hit(defender: Sprite, damage: int, push: float) -> None:
    """Change one fighter's health, show a small impact, and push them away."""
    global blue_health, impact, outcome, ruby_health
    if outcome != "Round 1":
        return
    if defender is blue:
        blue_health = max(0, blue_health - damage)
        defender.x = max(-330, defender.x - push)
    else:
        ruby_health = max(0, ruby_health - damage)
        defender.x = min(330, defender.x + push)
    impact = (defender.x, defender.y + 95, stage.time + 0.18)
    stage.play(hit_sound, volume=0.25)
    if blue_health == 0:
        outcome = "Ruby wins! Press R for another round."
        blue.think("Good match!", seconds=1.5)
    elif ruby_health == 0:
        outcome = "Blue wins! Press R for another round."
        ruby.think("Good match!", seconds=1.5)


strike = Message[tuple[int, float, float]]("strike")


@stage.on_broadcast(strike)
def resolve_strike(event: Event[Stage, tuple[int, float, float]]) -> None:
    attacker = event.source
    if attacker is blue:
        defender = ruby
    elif attacker is ruby:
        defender = blue
    else:
        return
    damage, reach, push = event.data
    if isinstance(attacker, Sprite) and close_enough(attacker, defender, reach):
        hit(defender, damage, push)


@stage.on_start
def start_music(event: Event[Stage, None]) -> None:
    # The stage owns this looping voice and stops it when the game closes.
    stage.play(dojo_theme, volume=0.22, loop=True)


# A script changes costume, waits for the hit moment, then returns to standing.
blue_punch = Script(Sprite)
blue_punch.set_costume(teal_frames[1])
blue_punch.wait(0.12)
blue_punch.play_sound(punch_sound, volume=0.4, wait=False)
blue_punch.broadcast(strike, (12, 145.0, 32.0))
blue_punch.wait(0.18)
blue_punch.set_costume(teal_frames[0])
blue_kick = Script(Sprite)
blue_kick.set_costume(teal_frames[2])
blue_kick.wait(0.18)
blue_kick.play_sound(kick_sound, volume=0.4, wait=False)
blue_kick.broadcast(strike, (18, 175.0, 46.0))
blue_kick.wait(0.25)
blue_kick.set_costume(teal_frames[0])
ruby_punch = Script(Sprite)
ruby_punch.set_costume(ruby_frames[1])
ruby_punch.wait(0.12)
ruby_punch.play_sound(punch_sound, volume=0.4, wait=False)
ruby_punch.broadcast(strike, (12, 145.0, 32.0))
ruby_punch.wait(0.18)
ruby_punch.set_costume(ruby_frames[0])
ruby_kick = Script(Sprite)
ruby_kick.set_costume(ruby_frames[2])
ruby_kick.wait(0.18)
ruby_kick.play_sound(kick_sound, volume=0.4, wait=False)
ruby_kick.broadcast(strike, (18, 175.0, 46.0))
ruby_kick.wait(0.25)
ruby_kick.set_costume(ruby_frames[0])


@blue.on_key_down(Key.W)
def blue_jump(event: Event[Sprite, Key]) -> None:
    global blue_speed_y
    if outcome == "Round 1" and blue.y == ground_y and ready(blue_attack):
        blue_speed_y = 620


@ruby.on_key_down(Key.UP)
def ruby_jump(event: Event[Sprite, Key]) -> None:
    global ruby_speed_y
    if outcome == "Round 1" and ruby.y == ground_y and ready(ruby_attack):
        ruby_speed_y = 620


@blue.on_key_down(Key.F)
def start_blue_punch(event: Event[Sprite, Key]) -> Action | None:
    global blue_attack
    if outcome == "Round 1" and ready(blue_attack):
        blue_attack = blue.act(blue_punch)
        return blue_attack
    return None


@blue.on_key_down(Key.G)
def start_blue_kick(event: Event[Sprite, Key]) -> Action | None:
    global blue_attack
    if outcome == "Round 1" and ready(blue_attack):
        blue_attack = blue.act(blue_kick)
        return blue_attack
    return None


@ruby.on_key_down(Key.K)
def start_ruby_punch(event: Event[Sprite, Key]) -> Action | None:
    global ruby_attack
    if outcome == "Round 1" and ready(ruby_attack):
        ruby_attack = ruby.act(ruby_punch)
        return ruby_attack
    return None


@ruby.on_key_down(Key.L)
def start_ruby_kick(event: Event[Sprite, Key]) -> Action | None:
    global ruby_attack
    if outcome == "Round 1" and ready(ruby_attack):
        ruby_attack = ruby.act(ruby_kick)
        return ruby_attack
    return None


@stage.on_key_down(Key.R)
def restart(event: Event[Stage, Key]) -> None:
    global \
        blue_attack, \
        blue_health, \
        blue_speed_y, \
        impact, \
        outcome, \
        ruby_attack, \
        ruby_health, \
        ruby_speed_y
    blue.stop()
    ruby.stop()
    blue.position = (-190, ground_y)
    ruby.position = (190, ground_y)
    blue.costume = teal_frames[0]
    ruby.costume = ruby_frames[0]
    blue_health = 100
    ruby_health = 100
    blue_speed_y = 0
    ruby_speed_y = 0
    blue_attack = None
    ruby_attack = None
    impact = None
    outcome = "Round 1"


def move_fighter(fighter: Sprite, left: Key, right: Key, dt: float, other: Sprite) -> None:
    """Read two held keys and keep the fighters from passing through each other."""
    direction = 0
    if stage.keyboard.is_down(left):
        direction -= 1
    if stage.keyboard.is_down(right):
        direction += 1
    next_x = fighter.x + direction * 230 * dt
    if fighter is blue:
        fighter.x = max(-330, min(next_x, other.x - 85))
    else:
        fighter.x = min(330, max(next_x, other.x + 85))


def fall(fighter: Sprite, speed: float, dt: float) -> float:
    """Apply simple gravity and return the next upward/downward speed."""
    speed -= 1550 * dt
    fighter.y = max(ground_y, fighter.y + speed * dt)
    if fighter.y == ground_y:
        return 0
    return speed


# update runs many times each second. Held keys make walking feel smooth.
@stage.on_update
def update(event: Event[Stage, float]) -> None:
    dt = event.data
    global blue_speed_y, impact, ruby_speed_y
    if outcome == "Round 1":
        if ready(blue_attack):
            move_fighter(blue, Key.A, Key.D, dt, ruby)
        if ready(ruby_attack):
            move_fighter(ruby, Key.LEFT, Key.RIGHT, dt, blue)
        blue_speed_y = fall(blue, blue_speed_y, dt)
        ruby_speed_y = fall(ruby, ruby_speed_y, dt)
    if impact is not None and stage.time >= impact[2]:
        impact = None


# Canvas drawings stay above the painted arena and health bars stay easy to read.
@stage.on_draw
def draw(canvas: Canvas) -> None:
    canvas.rectangle(Bounds(-390, 175, -80, 207), color="#152238")
    canvas.rectangle(Bounds(80, 175, 390, 207), color="#152238")
    canvas.rectangle(Bounds(-386, 179, -386 + blue_health * 3, 203), color="#32c6c0")
    canvas.rectangle(Bounds(386 - ruby_health * 3, 179, 386, 203), color="#e45461")
    canvas.text("BLUE", (-385, 145), size=21, color="#91f6ee")
    canvas.text("RUBY", (315, 145), size=21, color="#ffd3d8")
    canvas.text(outcome, (-145, 188), size=22, color="#fff2bd")
    canvas.text("Blue: A/D move, W jump, F punch, G kick", (-380, -207), size=18)
    canvas.text("Ruby: arrows move/jump, K punch, L kick    R: restart", (-380, -185), size=18)
    if impact is not None:
        canvas.circle((impact[0], impact[1]), 24, color="#fff3b2", width=5)


if __name__ == "__main__":
    stage.run()
