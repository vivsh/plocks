"""Dataclass values belong to actors; ordinary handlers respond to shared scripts."""

from dataclasses import dataclass, field
from pathlib import Path

from plocks import Canvas, Event, Key, Message, Script, Sprite, Stage


@dataclass
class PlayerState:
    health: int = 100
    speed: float = 1
    status: str = "Ready"
    hits: list[int] = field(default_factory=list[int])


@dataclass
class GameState:
    score: int = 0
    reports: int = 0


assets = Path(__file__).resolve().with_name("assets")
stage = Stage(background="#172d46", state=GameState)
first = Sprite(assets / "hero.png", x=-120, y=-40, state=PlayerState)
second = Sprite(assets / "hero.png", x=40, y=40, state=PlayerState)
second.state.health = 40
stage.add(first)
stage.add(second)
damage = Message[int]("take damage")
finished = Message[None]("trip finished")
trip = (
    Script(Sprite)
    .wait(0.15)
    .broadcast(damage, 10, wait=True)
    .glide_by(x=60, seconds=0.25)
    .broadcast(finished)
)
first.on_key_down(Key.SPACE, trip)
second.on_key_down(Key.SPACE, trip)


@first.on_broadcast(damage)
@second.on_broadcast(damage)
def take_damage(event: Event[Sprite[PlayerState], int]) -> None:
    # Each actor responds to its own script's message; state changes are normal Python.
    actor = event.target
    if event.source is not actor:
        return
    actor.state.health -= event.data
    actor.state.speed = 0.5
    actor.state.status = "Low health" if actor.state.health < 50 else "Healthy"
    actor.state.hits.append(event.data)


@first.on_key_down(Key.H)
def hit(event: Event[Sprite[PlayerState], Key]) -> None:
    event.target.state.health -= 1


@stage.on_broadcast(finished)
def report(event: Event[Stage[GameState], None]) -> None:
    event.target.state.score += 1
    event.target.state.reports += 1


@stage.on_key_down(Key.P)
def pause(event: Event[Stage[GameState], Key]) -> None:
    if event.target.paused:
        event.target.resume()
    else:
        event.target.pause()


@stage.on_draw
def draw(canvas: Canvas) -> None:
    canvas.text("SPACE: run   H: hit first   P: pause", (-225, 150), size=20)
    canvas.text(f"First: {first.state.health} / {first.state.status}", (-225, -100), size=20)
    canvas.text(f"Second: {second.state.health} / {second.state.status}", (-225, -125), size=20)
    canvas.text(
        f"Score: {stage.state.score}   Reports: {stage.state.reports}", (-225, -150), size=20
    )


if __name__ == "__main__":
    stage.run()
