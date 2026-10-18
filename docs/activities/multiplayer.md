# Play on two computers

[Home](../index.md) · [Activities](index.md)

One computer runs the game. Your friend's computer sends controls and shows the
same game picture. Both players see the host's scores, with a small delay.
**Sound plays on the host only.** Use a trusted home network.

## Get ready

Ask a grown-up to install Plocks with its **network** extra on both computers.
From a Plocks source checkout, use `python -m pip install -e ".[network]"`.
The package has not been released to PyPI.

Copy a starting project:

```sh
plocks examples platformer --copy-to two-players
```

Keep its assets. Replace its `main.py` with:

```python
from pathlib import Path

from plocks import Canvas, Event, GamepadButton, GamepadPress, Multiplayer, Sprite, Stage

assets = Path(__file__).parent / "assets"
stage = Stage(gamepad_count=2)
players = [Sprite(assets / "hero.png"), Sprite(assets / "checkpoint.png")]
scores = [0, 0]

for number, player in enumerate(players):
    player.position = (-100 + number * 200, 0)
    stage.add(player)


@stage.on_update
def walk(event: Event[Stage, float]) -> None:
    # Each player uses their own controls. Remote controls work the same way.
    for player, controls in zip(players, stage.gamepads):
        player.x += controls.left_stick[0] * 140 * event.data


@stage.on_button_down(GamepadButton.A)
def collect(event: Event[Stage, GamepadPress]) -> None:
    # For this little test, pressing A adds a point.
    scores[event.data.gamepad.index] += 1


@stage.on_draw
def draw_scores(canvas: Canvas) -> None:
    canvas.text(f"Player 1: {scores[0]}   Player 2: {scores[1]}", (-220, 160))


def main() -> None:
    stage.run(multiplayer=Multiplayer(slots=(1,)))


if __name__ == "__main__":
    main()
```

## Join your friend

1. On the host computer, run `python main.py`. Keep its game window active.
2. Find the host's LAN address in the computer's network settings. Copy the code
   printed in the terminal.
3. On the other computer, run `plocks join 192.168.1.20 --player 2`, using the
   host's address. Paste the connection code when asked.

Both players use **A/D** to move and **Space** to add a point. Physical controllers
also work. Player two's host slot is reserved: the host's keys cannot drive it.

`slots=(1,)` uses Python counting: slot **1** is player **2**.
Normal game code needs no score broadcasts or network callbacks.

**Try it:** change the scoring rule so a point needs a coin or a successful tag!

## If something goes wrong

- Use the same trusted LAN. Ask a grown-up about the host's firewall permission.
- Check the numeric address, port, code, and player number. Don't use `0.0.0.0`
  as the joining address.
- Release the controls while connecting. Play starts after the first picture.
- Pausing or minimizing the host pauses the shared game. Switching away from a
  joining window releases its controls.
- A failed connection ends the session with an error rather than leaving a
  character moving forever. Run the join command again for a fresh connection.

Both players share the host's camera. Pointer clicks/swipes are not forwarded.
Plain connections are for trusted LANs; manual internet use requires an encrypted
tunnel arranged by a grown-up. Don't expose the plain port publicly.
