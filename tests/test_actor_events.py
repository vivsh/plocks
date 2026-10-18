"""Actor registries retain scope and lifetime under Action/group authoring."""

from collections.abc import Iterator

import pytest
from PIL import Image

from plocks import (
    Action,
    Event,
    GamepadButton,
    GamepadPress,
    Key,
    Message,
    Script,
    Sprite,
    Stage,
    StageError,
    WhenBusy,
)
from plocks._runtime import close, dispatch
from plocks._scripts import _step, _trigger
from tests.test_scripts import ticks


@pytest.fixture
def game() -> Iterator[tuple[Stage, Sprite]]:
    stage = Stage()
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    hero = Sprite(Image.new("RGBA", (8, 8)))
    stage.add(hero)
    yield stage, hero
    close(stage)


def test_startup_snapshot_and_attachment(game: tuple[Stage, Sprite]) -> None:
    stage, hero = game
    group = Script(Sprite).move(12)
    hero.on_start(group)
    group.move(2)
    stage._state = "running"
    for handler in tuple(stage._starts):
        _trigger(stage, handler)
    ticks(stage, 2)
    assert hero.x == 14
    with pytest.raises(StageError, match="before run"):
        hero.on_start(group)
    stage.remove(hero)
    with pytest.raises(StageError):
        hero.on_button_down(GamepadButton.A, group, gamepad=stage.gamepads[0])
    stage.add(hero)
    ticks(stage, 2)
    assert hero.x == 14


@pytest.mark.parametrize("busy", [WhenBusy.IGNORE, WhenBusy.RESTART])
def test_busy_and_detach(game: tuple[Stage, Sprite], busy: WhenBusy) -> None:
    stage, hero = game
    hero.on_button_down(
        GamepadButton.A,
        Script(Sprite).glide_by(x=60, seconds=1),
        when_busy=busy,
        gamepad=stage.gamepads[0],
    )
    stage._state = "running"
    stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.A))
    dispatch(stage)
    ticks(stage, 30)
    old = stage._actions[0]
    stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.A))
    dispatch(stage)
    assert old.cancelled is (busy is WhenBusy.RESTART)
    ticks(stage, 65)
    assert hero.x == (60 if busy is WhenBusy.IGNORE else 90)
    stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.A))
    dispatch(stage)
    ticks(stage, 3)
    stage.remove(hero)
    assert not stage._actions
    stage._pending.append(GamepadPress(stage.gamepads[0], GamepadButton.A))
    dispatch(stage)
    assert not stage._actions


def test_typed_receiver_failure_and_none_not_busy(game: tuple[Stage, Sprite]) -> None:
    stage, hero = game
    channel = Message[int]("score")
    received: list[int] = []

    @hero.on_broadcast(channel)
    def receive(event: Event[Sprite, int]) -> None:
        value = event.data
        received.append(value)
        hero.say(str(value), seconds=1)

    stage._state = "running"
    stage.broadcast(channel, 1)
    stage.broadcast(channel, 2)
    ticks(stage, 4)
    assert received == [1, 2]
    assert hero._bubble is not None
    error = LookupError("original")
    other = Message[int]("failure")

    @hero.on_broadcast(other)
    def fail(event: Event[Sprite, int]) -> Action:
        raise error

    stage.broadcast(other, 0)
    _step(stage)
    with pytest.raises(LookupError) as caught:
        ticks(stage, 1)
    assert caught.value is error
