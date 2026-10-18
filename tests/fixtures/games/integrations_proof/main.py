"""Imported artwork and level, combined input, and independent motion."""

from pathlib import Path

from plocks import (
    Action,
    Canvas,
    Ease,
    Event,
    GamepadButton,
    GamepadLayout,
    GamepadPress,
    Key,
    PixeloramaSheet,
    Sprite,
    Stage,
    TiledMap,
)

assets = Path(__file__).resolve().parent / "assets"
stage = Stage(width=480, height=360, background="#203548")
level = TiledMap(assets / "jungle.tmj", x=-160, y=64, layer=-1)
for tilemap in level.layers.values():
    stage.add(tilemap)
art = PixeloramaSheet(assets / "hero.png")
hero = Sprite(art.frames[0])
hero.position = level.points["Spawns/player_start"]
stage.add(hero)
friend = Sprite(art.frames[0], x=-150, y=110)
stage.add(friend)
player = stage.gamepads[0]
player.map_key(Key.SPACE, GamepadButton.A)
player.map_left_stick(left=Key.LEFT, right=Key.RIGHT)
hero.on_start(art.animation("walk").repeat())
jump = hero.sequence()
jump.glide_by(y=60, seconds=0.2, easing=Ease.OUT)
jump.glide_by(y=-60, seconds=0.2, easing=Ease.IN)
presses = 0
second_presses = 0
turbo_presses = 0
second = stage.gamepads[1]
second.layout = GamepadLayout.NINTENDO
second.map_key(Key.ENTER, GamepadButton.A)
player.map_key(Key.F, GamepadButton.B)


@friend.on_gamepad_button_down(GamepadButton.A, gamepad=second)
def second_pressed(event: Event[Sprite, GamepadPress]) -> None:
    global second_presses
    second_presses += 1


@hero.on_gamepad_button_down(GamepadButton.B, gamepad=player, repeat=0.05)
def turbo_pressed(event: Event[Sprite, GamepadPress]) -> None:
    global turbo_presses
    turbo_presses += 1


@hero.on_gamepad_button_down(GamepadButton.A, gamepad=player)
def jump_pressed(event: Event[Sprite, GamepadPress]) -> Action:
    global presses
    presses += 1
    return event.target.act(jump)


@friend.on_update
def patrol(event: Event[Sprite, float]) -> None:
    event.target.x = -150 + (stage.time * 60) % 300


@stage.on_key_down(Key.P)
def pause(event: Event[Stage, Key]) -> None:
    if stage.paused:
        stage.resume()
    else:
        stage.pause()


@stage.on_key_down(Key.ESCAPE)
def quit_game(event: Event[Stage, Key]) -> None:
    stage.stop()


@stage.on_draw
def draw(canvas: Canvas) -> None:
    canvas.text("Arrows: move    Space / A: jump    P: pause", (-225, 160), size=18)
    canvas.text(f"Jump presses: {presses}", (-225, -145), size=20)


if __name__ == "__main__":
    stage.run()
