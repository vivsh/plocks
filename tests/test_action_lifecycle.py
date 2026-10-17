"""Bounded work, dependency safety, cancellation and resource cleanup."""

import asyncio
from collections.abc import Iterator
from dataclasses import fields
from typing import cast

import pytest
from PIL import Image

from plocks import Action, ActionCancelled, Canvas, Key, Sound, Sprite, Stage, StageError
from plocks._runtime import close, dispatch, drive
from plocks._scripts import _step
from tests.test_groups import ticks


@pytest.fixture
def game() -> Iterator[tuple[Stage, Sprite]]:
    stage = Stage()
    hero = Sprite(Image.new("RGBA", (8, 8)))
    stage.add(hero)
    stage._state = "running"
    yield stage, hero
    close(stage)


def test_sibling_dependency_cycle_fails_instead_of_hanging(game: tuple[Stage, Sprite]) -> None:
    stage, _ = game

    def first_call() -> Action:
        return second

    def second_call() -> Action:
        return first

    first = stage.call(first_call)
    second = stage.call(second_call)
    with pytest.raises(StageError, match="ancestor"):
        _step(stage)


def test_await_cancel_can_be_caught_without_duplicate_work(game: tuple[Stage, Sprite]) -> None:
    stage, hero = game
    canceled = hero.wait(1)
    canceled.cancel()
    seen: list[str] = []

    @hero.on_key_down(Key.A)
    async def handle() -> None:
        try:
            await canceled
        except ActionCancelled:
            seen.append("caught")

    stage._pending.append(Key.A)
    dispatch(stage)
    ticks(stage, 2)
    assert seen == ["caught"] and not stage._actions


def test_self_stop_and_cleanup_once(game: tuple[Stage, Sprite]) -> None:
    stage, hero = game
    cleaned: list[str] = []

    @hero.on_key_down(Key.A)
    async def handle() -> None:
        try:
            hero.stop()
            await hero.wait(1)
        finally:
            cleaned.append("closed")

    stage._pending.append(Key.A)
    dispatch(stage)
    ticks(stage, 2)
    assert cleaned == ["closed"] and not stage._actions


def test_borrowed_action_survives_observer_cancellation(game: tuple[Stage, Sprite]) -> None:
    stage, hero = game
    shared = hero.glide_by(x=20, seconds=1)

    @stage.on_key_down(Key.A)
    async def observe() -> None:
        await shared

    stage._pending.append(Key.A)
    dispatch(stage)
    ticks(stage, 2)
    observer = next(a for a in stage._actions if a is not shared)
    observer.cancel()
    ticks(stage, 65)
    assert shared.done and not shared.cancelled and hero.x == 20


def test_limit_rejects_admission_and_empty_nested_loop(game: tuple[Stage, Sprite]) -> None:
    _, hero = game
    for _ in range(128):
        hero.wait(10)
    with pytest.raises(StageError, match="128"):
        hero.wait(10)
    hero.stop()
    group = hero.sequence().move(1)
    for _ in range(40):
        try:
            group = hero.sequence().act(group)
        except ValueError as error:
            assert "32" in str(error)
            break
    else:
        pytest.fail("Missing plan depth limit")


def test_unsupported_await_is_actionable(game: tuple[Stage, Sprite]) -> None:
    stage, hero = game

    @hero.on_key_down(Key.A)
    async def bad() -> None:
        await asyncio.sleep(0)

    stage._pending.append(Key.A)
    dispatch(stage)
    with pytest.raises(StageError, match="Plocks operations"):
        _step(stage)
    assert not stage._actions


def test_sound_wait_cancel_stops_only_its_voice(game: tuple[Stage, Sprite]) -> None:
    from pathlib import Path

    stage, hero = game
    sound = Sound(Path(__file__).parents[1] / "tests/fixtures/games/proof/assets/tone.ogg")
    first = hero.play_sound(sound)
    second = hero.play_sound(sound)
    _step(stage)
    assert len(stage._voices) == 2
    first.cancel()
    assert stage._voices[0].finished and not stage._voices[1].finished
    second.cancel()
    assert all(v.finished for v in stage._voices)


def test_original_failure_survives_cleanup_and_cancellation(game: tuple[Stage, Sprite]) -> None:
    stage, hero = game
    import pygame

    stage._target = pygame.display.set_mode((480, 360))
    original = ValueError("original")

    @hero.on_key_down(Key.A)
    async def bad() -> None:
        try:
            await hero.wait(10)
        finally:
            raise LookupError("cleanup")

    stage._pending.append(Key.A)
    dispatch(stage)
    ticks(stage, 2)

    @stage.on_update
    def fail(dt: float) -> None:
        raise original

    async def check() -> None:
        with pytest.raises(ValueError) as caught:
            await drive(stage)
        assert caught.value is original

    asyncio.run(check())
    assert not stage._actions and hero._stage is None
    assert any("cleanup" in note for note in original.__notes__)


def test_update_draw_reject_actions_at_runtime(game: tuple[Stage, Sprite]) -> None:
    from collections.abc import Callable

    from plocks._runtime import advance

    stage, hero = game

    def wrong(dt: float) -> Action:
        return hero.wait(1)

    stage.on_update(cast(Callable[[float], None], wrong))
    stage._last_wall = 0
    with pytest.raises(TypeError, match="return None"):
        advance(stage, 0.02)

    async def wrong_draw(canvas: Canvas) -> None:
        pass

    with pytest.raises(TypeError, match="synchronous"):
        stage.on_draw(cast(Callable[[Canvas], None], wrong_draw))


def test_actual_field_inventory_has_no_parallel_lifecycle(game: tuple[Stage, Sprite]) -> None:
    from plocks._scripts import _Fiber, _Handler
    from plocks.actions import _Completion, _Queued
    from plocks.geometry import _Placement
    from plocks.groups import Group, SpriteGroup
    from plocks.physics import Body, Physics

    stage, hero = game
    assert set(Action.__slots__) == {"_stage", "_actor", "_after", "_parent", "_handler", "_state"}
    assert {f.name for f in fields(_Fiber)} == {"coroutine", "waiting", "children"}
    assert {f.name for f in fields(_Handler)} == {"start", "actor", "when_busy"}
    assert {f.name for f in fields(_Queued)} == {"work", "admitted_at"}
    assert {f.name for f in fields(_Completion)} == {"at", "result"}
    assert {f.name for f in fields(_Placement)} == {"position", "direction", "body_type"}
    assert set(Group.__slots__) == {"_actor", "_times", "_commands"} and SpriteGroup.__slots__ == ()
    assert set(Body.__slots__) == {"_actor", "_world", "_native", "_shape"}
    assert set(Physics.__slots__) == {"_stage", "_space", "_bodies", "_terrain"}
    assert not hasattr(hero, "_x") and not hasattr(stage, "_runs")


def test_message_join_cycle_reports_ancestor(game: tuple[Stage, Sprite]) -> None:
    from plocks import Signal
    from plocks._scripts import _deliver

    stage, _ = game
    signal = Signal("cycle")

    @stage.on_message(signal)
    def receive() -> Action:
        return sender

    sender = stage.broadcast_and_wait(signal)
    _step(stage)
    _deliver(stage)
    with pytest.raises(StageError, match="ancestor"):
        ticks(stage, 3)


def test_call_validates_before_admission(game: tuple[Stage, Sprite]) -> None:
    from collections.abc import Callable

    stage, hero = game
    with pytest.raises(TypeError, match="function"):
        hero.call(cast(Callable[[], None], 12))
    assert not stage._actions
