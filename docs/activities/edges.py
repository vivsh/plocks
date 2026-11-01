"""Move a dinosaur to the yellow rectangle and screen edges."""

from pathlib import Path

from plocks import (
    Bounds,
    Canvas,
    Edge,
    Event,
    GamepadButton,
    GamepadPress,
    Image,
    Key,
    Label,
    Sprite,
    Stage,
)

assets = Path(__file__).resolve().parent / "assets"
stage = Stage(background="#18324a")
player = stage.gamepads[0]
player.map_left_stick(left=Key.LEFT, right=Key.RIGHT, up=Key.UP, down=Key.DOWN)
player.map_key(Key.SPACE, GamepadButton.A)
arena = Bounds(-140, -90, 140, 90)
hero = Sprite(Image(assets / "dinosaur.png").resized(48, 48))
stage.add(hero)
level_text = Label("Yellow rectangle: not reached yet", position=(0, 152), size=18)
view_text = Label("Screen edge: not reached yet", position=(0, 127), size=18)
stage.add(level_text)
stage.add(view_text)
stage.add(Label("Arrows: move     Space: return home", position=(0, -150), size=18))


@hero.on_update
def move(event: Event[Sprite, float]) -> None:
    # Read held directions every game step, so arrows keep moving us.
    dx, dy = player.left_stick
    event.target.x += dx * 150 * event.data
    event.target.y += dy * 150 * event.data


@hero.on_edge(arena)
def reached_rectangle(event: Event[Sprite, frozenset[Edge]]) -> None:
    sides = ", ".join(sorted(edge.value for edge in event.data))
    level_text.text = f"Yellow rectangle: {sides}"


@hero.on_edge()
def reached_screen(event: Event[Sprite, frozenset[Edge]]) -> None:
    sides = ", ".join(sorted(edge.value for edge in event.data))
    view_text.text = f"Screen edge: {sides}"


@hero.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])
def home(event: Event[Sprite, GamepadPress]) -> None:
    event.target.position = (0, 0)
    level_text.text = "Yellow rectangle: not reached yet"
    view_text.text = "Screen edge: not reached yet"


@stage.on_draw
def draw(canvas: Canvas) -> None:
    # Our camera stays at the origin, so this outline matches the world rectangle.
    canvas.rectangle(arena, color="gold", width=2)


if __name__ == "__main__":
    stage.run()
