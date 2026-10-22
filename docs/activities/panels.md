# Give your controls a home

[Home](../index.md) · [More activities](index.md)

A **Panel** is a colored box containing labels, buttons and health bars. Move the
panel and its controls move together. The camera never moves it.

## Make a tiny health game

With Plocks installed, save this as `main.py` and run `python main.py`.
You need no pictures. Click the button, or press Space. What happens at zero?

```python
from plocks import (
    AlertLevel, Anchor, Button, Event, Label, Panel, ProgressBar, Stage, UITheme,
)

stage = Stage(background="midnightblue", ui_theme=UITheme(accent_color="orange"))

# The panel's top-left corner sits here on the screen.
menu = Panel(position=(-220, 160), width=280, height=180, anchor=Anchor.TOP_LEFT)
heading = Label("Health: 100", position=(-120, 65), anchor=Anchor.TOP_LEFT)
health = ProgressBar(value=100, position=(-120, 5), width=240, anchor=Anchor.CENTER_LEFT)
hit = Button("Lose 25 health", position=(0, -50), width=220)

# Inside a panel, (0, 0) is its center. x goes right and y goes up.
menu.add(heading)
menu.add(health)
menu.add(hit)
stage.add(menu)
stage.focus(hit)


def play_again(event: Event[Stage, None]) -> None:
    health.value = 100
    heading.text = "Health: 100"


@hit.on_click
def lose_health(event: Event[Button, None]) -> None:
    health.value = max(0, health.value - 25)
    heading.text = f"Health: {int(health.value)}"
    if health.value == 0:
        stage.alert(
            "Game over! Try another round.",
            level=AlertLevel.ERROR,
            button_text="Play again",
            on_close=play_again,
        )


if __name__ == "__main__":
    stage.run()
```

## Try a change

- Move the whole menu: `menu.position = (0, 0)`.
- Hide it with `menu.visible = False`; show it with `True`.
- Try `menu.color = (20, 40, 70, 200)`. The last number is opacity, from 0 to 255.
- Use `menu.remove(hit)` to detach a control, or `menu.clear()` to empty it.

Add children to the panel, then add the panel to the stage. A child belongs to one
place at a time. Controls outside the panel's rectangle are clipped; panels cannot
contain other panels.

## Keep a matching style

`UITheme` gives controls shared colors, text size, padding and rounded corners.
Replace `stage.ui_theme` to change the look while playing:

```python
stage.ui_theme = UITheme(accent_color="cyan", panel_color="#24384b", text_size=28)
```

A control's own setting wins: `heading.color = "gold"`. Assign `None` to inherit
again. If you choose much bigger button text, increase the button's height too.

[Next: show an alert](alerts.md)
