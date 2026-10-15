"""Dialogue shares simulation timing, cancellation and the ordinary render target."""

import asyncio
from collections.abc import Iterator
from dataclasses import fields
from typing import cast

import pygame
import pytest
from PIL import Image

from plocks import (
    Actor,
    Canvas,
    ClearBubble,
    Costume,
    During,
    GlideBy,
    Key,
    Loop,
    Move,
    Puppet,
    Repeat,
    RotationStyle,
    Say,
    Script,
    Sequence,
    Sprite,
    Stage,
    StageError,
    Think,
    Wait,
)
from plocks._bubbles import _draw_bubble, _layout, _wrap_text
from plocks._operations import _BubbleRun, _freeze
from plocks._render import frame
from plocks._runtime import close, dispatch
from plocks._scripts import _sample, _step


def test_speech_first_path() -> None:
    """Timed speech follows movement; pause freezes both and cleanup releases the slot."""
    stage = Stage(background="navy")
    hero = Sprite(Image.new("RGBA", (20, 20), "orange"))
    friend = Sprite(hero.costume, y=-100)
    stage.add(hero)
    stage.add(friend)
    stage._state = "running"
    stage._target = pygame.display.set_mode((480, 360))
    recipe = During(GlideBy(x=60, seconds=1), meanwhile=Say("Hello", seconds=1))
    try:
        hero.act(recipe)
        assert hero._bubble is None
        _step(stage)
        operation = hero._bubble
        assert isinstance(operation, _BubbleRun)
        assert {f.name for f in fields(operation)} == {"actor", "definition", "deadline"}
        for _ in range(30):
            stage._tick += 1
            _sample(stage)
            _step(stage)
            friend.move(1)
        assert hero.x == 30 and friend.x == 30
        frame(stage)
        assert (
            sum(
                stage._target.get_at((x, y))[:3] == (255, 255, 255)
                for x in range(240, 300)
                for y in range(125, 160)
            )
            > 100
        )
        stage.pause()
        _step(stage)
        assert hero._bubble is operation and hero.x == 30
        stage.resume()
        hero.act(Say("Replacement", seconds=1))
        _step(stage)
        replacement = hero._bubble
        assert replacement is not operation
        _freeze(operation, stage.time, cancel=True)
        assert hero._bubble is replacement
        stage._tick += 60
        _sample(stage)
        _step(stage)
        assert hero._bubble is None and hero.x == 30
    finally:
        close(stage)
    assert not stage._runs and hero._stage is None and hero._bubble is None


def test_invalid_speech_keeps_running_writer() -> None:
    """Validation never interrupts an existing behavior."""
    stage = Stage()
    hero = Sprite(Image.new("RGBA", (4, 4), "red"))
    stage.add(hero)
    stage._state = "running"
    try:
        hero.act(Say("Hello", seconds=2))
        _step(stage)
        original = hero._bubble
        with pytest.raises(ValueError):
            hero.act(Say("Invalid", seconds=float("nan")))
        assert hero._bubble is original and len(stage._runs) == 1
    finally:
        close(stage)


@pytest.fixture
def game() -> Iterator[tuple[Stage, Sprite, Puppet]]:
    """Provide both actor targets with a deterministic simulation and render target."""
    stage = Stage(background="navy")
    hero = Sprite(Image.new("RGBA", (20, 20), "orange"))
    puppet = Puppet.stick_figure()
    puppet.x = 100
    stage.add(hero)
    stage.add(puppet)
    stage._state = "running"
    stage._target = pygame.display.set_mode((480, 360))
    try:
        yield stage, hero, puppet
    finally:
        close(stage)


def tick(stage: Stage, count: int = 1) -> None:
    """Advance exact eligible ticks, including script sampling and dispatch."""
    for _ in range(count):
        if stage.paused:
            dispatch(stage)
            continue
        stage._tick += 1
        _sample(stage)
        dispatch(stage)
        _step(stage)


@pytest.mark.parametrize("puppet_target", [False, True])
def test_persistent_and_timed_forms(
    game: tuple[Stage, Sprite, Puppet], puppet_target: bool
) -> None:
    """Both actor types share persistence, replacement and precise completion semantics."""
    stage, hero, puppet = game
    actor: Actor = puppet if puppet_target else hero
    actor.say("first")
    assert isinstance(actor._bubble, Say)
    actor.think("second")
    assert isinstance(actor._bubble, Think)
    actor.act(Sequence(Say("third"), Wait(0.1), ClearBubble(), Think("done", seconds=0.1)))
    _step(stage)
    assert isinstance(actor._bubble, Say) and actor._bubble.text == "third"
    tick(stage, 6)
    assert isinstance(actor._bubble, _BubbleRun)
    assert isinstance(actor._bubble.definition, Think)
    tick(stage, 6)
    assert actor._bubble is None and not stage._runs
    actor.act(Say("stay"))
    _step(stage)
    actor.stop()
    assert isinstance(actor._bubble, Say)
    actor.clear_bubble()
    actor.clear_bubble()
    assert actor._bubble is None


def test_definition_reuse_fractional_and_zero(game: tuple[Stage, Sprite, Puppet]) -> None:
    """Reusable definitions have independent identities; seven fractional waits take one second."""
    stage, hero, puppet = game
    recipe = Say("shared", seconds=1 / 7)
    hero.act(Repeat(7, recipe))
    _step(stage)
    first = hero._bubble
    tick(stage, 10)
    puppet.act(recipe)
    _step(stage)
    assert hero._bubble is not puppet._bubble and hero._bubble is not first
    tick(stage, 50)
    assert hero._bubble is None and puppet._bubble is None and not stage._runs
    hero.act(Sequence(Say("zero", seconds=0), Say("after")))
    _step(stage)
    assert isinstance(hero._bubble, _BubbleRun)
    tick(stage)
    assert isinstance(hero._bubble, Say) and hero._bubble.text == "after"
    hero.act(Loop(Say("loop")))
    _step(stage)
    tick(stage, 3)
    assert len(stage._runs) == 1


def test_empty_timed_text_never_clears_new_speech(game: tuple[Stage, Sprite, Puppet]) -> None:
    """A blank timed block is clear plus wait, with no bubble claim or late cleanup."""
    stage, hero, _ = game
    hero.say("before")
    hero.act(Say(" \n\t", seconds=0.5))
    _step(stage)
    assert hero._bubble is None
    hero.say("newer")
    tick(stage, 30)
    assert isinstance(hero._bubble, Say) and hero._bubble.text == "newer"
    hero.think("")
    assert hero._bubble is None


def test_same_definition_restart_and_expired_cleanup(game: tuple[Stage, Sprite, Puppet]) -> None:
    """Request identity, not reusable definition identity, guards completion cleanup."""
    stage, hero, _ = game
    recipe = Say("same", seconds=1)
    hero.act(recipe)
    _step(stage)
    original = hero._bubble
    assert isinstance(original, _BubbleRun)
    hero.act(recipe, restart=True)
    _step(stage)
    replacement = hero._bubble
    assert replacement is not original
    _freeze(original, stage.time, cancel=True)
    assert hero._bubble is replacement
    stage._tick = 60
    hero.say("at deadline")
    _step(stage)
    assert isinstance(hero._bubble, Say) and hero._bubble.text == "at deadline"


@pytest.mark.parametrize("clear", [False, True])
def test_immediate_replacement_cancels_whole_root(
    game: tuple[Stage, Sprite, Puppet], clear: bool
) -> None:
    """A direct bubble edit cancels related movement and skips the rest of that root."""
    stage, hero, puppet = game
    hero.act(
        Sequence(During(GlideBy(x=60, seconds=1), meanwhile=Think("busy", seconds=2)), Move(999))
    )
    puppet.act(GlideBy(y=60, seconds=1))
    _step(stage)
    tick(stage, 15)
    if clear:
        hero.clear_bubble()
    else:
        hero.say("new")
    frozen = hero.x
    tick(stage, 60)
    assert hero.x == frozen and puppet.y == 60
    assert (hero._bubble is None) is clear


def test_during_conflict_and_background_scope(game: tuple[Stage, Sprite, Puppet]) -> None:
    """Timed siblings conflict; scoped timed backgrounds clear, persistent backgrounds survive."""
    stage, hero, _ = game
    hero.act(During(Say("one", seconds=1), meanwhile=Think("two", seconds=1)))
    with pytest.raises(StageError, match="same property"):
        _step(stage)
    hero.stop()
    assert hero._bubble is None
    hero.act(During(Wait(0.1), meanwhile=Say("timed", seconds=10)))
    _step(stage)
    tick(stage, 6)
    assert hero._bubble is None
    hero.act(During(Wait(0.1), meanwhile=Say("persistent")))
    _step(stage)
    tick(stage, 6)
    assert isinstance(hero._bubble, Say)
    hero.act(During(Say("timed", seconds=1), meanwhile=ClearBubble()))
    _step(stage)
    assert hero._bubble is None and not stage._runs


def test_pause_hidden_offscreen_and_ui(game: tuple[Stage, Sprite, Puppet]) -> None:
    """Hidden bubbles still expire; paused synchronous input can replace them immediately."""
    stage, hero, _ = game
    hero.act(Say("pause", seconds=1))
    _step(stage)
    stage.pause()
    stage.on_key_down(Key.C)(hero.clear_bubble)
    stage._pending.append(Key.C)
    tick(stage)
    assert hero._bubble is None and stage.time == 0
    hero.act(Think("later", seconds=0.1))
    _step(stage)
    assert hero._bubble is None
    stage.resume()
    _step(stage)
    hero.visible = False
    tick(stage, 6)
    assert hero._bubble is None
    hero.visible = True
    hero.x = 1000
    hero.act(Say("off screen", seconds=0.1))
    _step(stage)
    tick(stage, 6)
    assert hero._bubble is None


def test_detach_and_failing_cleanup(game: tuple[Stage, Sprite, Puppet]) -> None:
    """Removal clears even finally-written dialogue and completes membership teardown on failure."""
    stage, hero, _ = game

    async def behavior(actor: Sprite) -> None:
        try:
            await Say("inside", seconds=10).run(actor)
        finally:
            actor.say("cleanup")
            raise LookupError("cleanup failed")

    hero.act(Script(behavior))
    _step(stage)
    with pytest.raises(LookupError, match="cleanup failed"):
        stage.remove(hero)
    assert hero._bubble is None and hero._stage is None and hero not in stage.objects
    assert not stage._runs
    stage.add(hero)
    assert hero._bubble is None
    stage.remove(hero)
    hero.think("explicit detached edit")
    stage.add(hero)
    assert isinstance(hero._bubble, Think)


def test_unbound_bubble_target_and_detached_rejection(game: tuple[Stage, Sprite, Puppet]) -> None:
    """Removal finds unbound scripts operating on the actor; detached block use fails."""
    stage, hero, _ = game

    @stage.on_key_down(Key.SPACE)
    async def speech() -> None:
        await Say("unbound", seconds=10).run(hero)

    stage._pending.append(Key.SPACE)
    dispatch(stage)
    _step(stage)
    assert stage._runs[0].actor is None
    stage.remove(hero)
    assert not stage._runs and hero._bubble is None
    stage._pending.append(Key.SPACE)
    dispatch(stage)
    with pytest.raises(StageError, match="membership"):
        _step(stage)


@pytest.mark.parametrize("seconds", [-1.0, float("nan"), float("inf")])
def test_duration_validation(seconds: float) -> None:
    """Both speech and thought reject invalid times at construction."""
    with pytest.raises(ValueError):
        Say("bad", seconds=seconds)
    with pytest.raises(ValueError):
        Think("bad", seconds=seconds)


def test_text_size_and_definition_inventory(game: tuple[Stage, Sprite, Puppet]) -> None:
    """Validation precedes mutation; immutable definitions store no execution fields."""
    stage, hero, _ = game
    hero.act(Say("valid", seconds=10))
    _step(stage)
    original = hero._bubble
    with pytest.raises(ValueError):
        hero.say("bad\x00text")
    with pytest.raises(TypeError):
        hero.think(cast(str, 123))
    with pytest.raises(ValueError):
        stage.bubble_text_size = 0
    with pytest.raises(TypeError):
        stage.bubble_text_size = True
    assert hero._bubble is original and stage.bubble_text_size == 24
    stage.bubble_text_size = 28
    assert hero._bubble is original
    assert {f.name for f in fields(Say("text"))} == {"text", "seconds"}
    assert {f.name for f in fields(Think("text"))} == {"text", "seconds"}
    assert fields(ClearBubble()) == ()


def test_wrapping_and_bounded_long_words() -> None:
    """Actual font measurements bound lines; newlines survive and overflow is ellipsized."""
    pygame.font.init()
    font = pygame.font.Font(None, 24)
    assert _wrap_text(font, "one\r\n\r\ntwo", 100, 4) == ("one", "", "two")
    assert _wrap_text(font, "a\tb", 100, 4) == ("a    b",)
    wrapped = _wrap_text(font, "word " * 1000, 90, 3)
    assert len(wrapped) == 3 and wrapped[-1].endswith("...")
    assert all(font.size(line)[0] <= 90 for line in wrapped)
    long_word = _wrap_text(font, "W" * 100000, 90, 2)
    assert len(long_word) == 2 and long_word[-1].endswith("...")
    assert all(font.size(line)[0] <= 90 for line in long_word)
    assert not _wrap_text(font, "hi", 0, 1)


@pytest.mark.parametrize("position", [(-230, 160), (230, 160), (-230, -160), (230, -160), (0, 0)])
def test_viewport_placement(game: tuple[Stage, Sprite, Puppet], position: tuple[int, int]) -> None:
    """Edge placement and long words stay within logical viewport margins."""
    stage, hero, _ = game
    hero.position = position
    hero.think("a long message " * 40)
    pygame.font.init()
    font = pygame.font.Font(None, stage.bubble_text_size)
    layout = _layout(stage, hero, font, "a long message " * 40)
    assert layout is not None
    body, lines, _ = layout
    assert body.left >= 8 and body.right <= stage.width - 8
    assert body.top >= 8 and body.bottom <= stage.height - 8
    assert lines and all(font.size(line)[0] <= body.width - 16 for line in lines)


def test_render_camera_visibility_and_overlays(game: tuple[Stage, Sprite, Puppet]) -> None:
    """Bubbles follow camera/transformed bounds and render before unchanged Canvas overlays."""
    stage, hero, puppet = game
    assert stage._target is not None
    target = stage._target
    puppet.visible = False
    hero.say("Hello")
    frame(stage)
    before = target.copy()
    stage.camera = (20, 0)
    frame(stage)
    assert target.get_at((220, 125)) == before.get_at((240, 125))
    hero.visible = False
    frame(stage)
    assert target.get_at((220, 125))[:3] == (0, 0, 128)
    hero.visible = True
    stage.camera = (0, 0)
    hero.scale = 2
    hero.direction = 0
    hero.rotation_style = RotationStyle.LEFT_RIGHT
    hero.costume = Costume(Image.new("RGBA", (40, 10), "orange"), anchor=(2, 3))
    frame(stage)
    clip = pygame.Rect(10, 10, 200, 200)
    target.set_clip(clip)
    _draw_bubble(stage, target, hero)
    assert target.get_clip() == clip
    target.set_clip(None)

    @stage.on_draw
    def cover(canvas: Canvas) -> None:
        canvas.rectangle(stage.bounds, color="red")
        canvas.text("Canvas still works", (0, 0))

    frame(stage)
    assert target.get_at((240, 125))[:3] == (255, 0, 0)


def test_puppet_render_and_thought_connector(game: tuple[Stage, Sprite, Puppet]) -> None:
    """Puppet attachments define placement; thought and speech connectors differ."""
    stage, hero, puppet = game
    hero.visible = False
    puppet.position = (0, -100)
    puppet.say("hello")
    frame(stage)
    assert stage._target is not None
    speech = pygame.image.tobytes(stage._target, "RGBA")
    puppet.think("hello")
    frame(stage)
    assert pygame.image.tobytes(stage._target, "RGBA") != speech
    rest = puppet.pose
    puppet.pose = rest.with_angles({"right_elbow": 60})
    puppet.scale = 0.8
    puppet.direction = 120
    frame(stage)
    assert isinstance(puppet._bubble, Think)


def test_tiny_viewport_and_huge_size() -> None:
    """Unavailable space suppresses text before allocating a huge font or surface."""
    stage = Stage(width=20, height=20, bubble_text_size=10**20)
    actor = Sprite(Image.new("RGBA", (4, 4), "red"))
    actor.say("hello")
    target = pygame.Surface((20, 20))
    target.fill("navy")
    _draw_bubble(stage, target, actor)
    assert target.get_at((10, 10))[:3] == (0, 0, 128)


def test_driver_failure_and_task_cancellation(game: tuple[Stage, Sprite, Puppet]) -> None:
    """Original callback errors and canceled outer tasks clear all bubble requests."""
    from plocks._runtime import drive

    stage, hero, puppet = game
    hero.act(Say("running", seconds=10))
    puppet.think("persistent")

    @stage.on_update
    def fail(dt: float) -> None:
        raise LookupError("original dialogue failure")

    async def exercise() -> None:
        with pytest.raises(LookupError, match="original dialogue failure"):
            await drive(stage)

    asyncio.run(exercise())
    assert hero._bubble is None and puppet._bubble is None and not stage._runs
    assert hero._stage is None and puppet._stage is None and stage._target is None

    fresh = Stage()
    fresh.add(hero)
    fresh._state = "running"
    fresh._target = pygame.display.set_mode((480, 360))
    hero.act(Think("cancel task", seconds=10))

    async def cancel() -> None:
        task = asyncio.create_task(drive(fresh))
        await asyncio.sleep(0)
        assert isinstance(hero._bubble, _BubbleRun)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel())
    assert hero._bubble is None and hero._stage is None and not fresh._runs
    assert fresh._target is None


def test_layer_order_and_oversized_actor(game: tuple[Stage, Sprite, Puppet]) -> None:
    """Bubble order uses layers then insertion; huge actors fall back to viewport placement."""
    stage, hero, puppet = game
    puppet.visible = False
    second = Sprite(hero.costume)
    stage.add(second)
    hero.say("AAAAAAAA")
    second.say("BBBBBBBB")
    frame(stage)
    assert stage._target is not None
    first_order = pygame.image.tobytes(stage._target, "RGBA")
    hero.layer = 1
    frame(stage)
    assert pygame.image.tobytes(stage._target, "RGBA") != first_order
    hero.layer = 0
    frame(stage)
    assert pygame.image.tobytes(stage._target, "RGBA") == first_order
    hero.scale = 100
    pygame.font.init()
    font = pygame.font.Font(None, 24)
    layout = _layout(stage, hero, font, "huge actor")
    assert layout is not None
    body, _, _ = layout
    assert 8 <= body.top <= body.bottom <= stage.height - 8
    frame(stage)


def test_reentrant_removal_in_cleanup(game: tuple[Stage, Sprite, Puppet]) -> None:
    """Synchronous finally code may remove its own actor without double-removal errors."""
    stage, hero, _ = game

    async def behavior(actor: Sprite) -> None:
        try:
            await Say("inside", seconds=10).run(actor)
        finally:
            stage.remove(actor)

    hero.act(Script(behavior))
    _step(stage)
    stage.remove(hero)
    assert hero not in stage.objects and hero._stage is None and hero._bubble is None
