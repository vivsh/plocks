"""Dialogue layout stays unchanged while commands use Action ownership."""

from collections.abc import Iterator
from dataclasses import fields
from typing import cast

import pygame
import pytest
from PIL import Image

from plocks import Canvas, Costume, Puppet, RotationStyle, Sprite, Stage
from plocks._bubbles import _draw_bubble, _layout, _wrap_text
from plocks._commands import _ClearBubble, _Say, _Think
from plocks._operations import _BubbleRun, _freeze
from plocks._render import frame
from plocks._runtime import close, dispatch
from plocks._scripts import _sample, _step


def test_invalid_speech_keeps_running_writer() -> None:
    """Validation never interrupts an existing behavior."""
    stage = Stage()
    hero = Sprite(Image.new("RGBA", (4, 4), "red"))
    stage.add(hero)
    stage._state = "running"
    try:
        hero.say("Hello", seconds=2)
        _step(stage)
        original = hero._bubble
        with pytest.raises(ValueError):
            hero.say("Invalid", seconds=float("nan"))
        assert hero._bubble is original and len(stage._actions) == 1
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


@pytest.mark.parametrize("seconds", [-1.0, float("nan"), float("inf")])
def test_duration_validation(seconds: float) -> None:
    """Both speech and thought reject invalid times at construction."""
    with pytest.raises(ValueError):
        _Say("bad", seconds=seconds)
    with pytest.raises(ValueError):
        _Think("bad", seconds=seconds)


def test_text_size_and_definition_inventory(game: tuple[Stage, Sprite, Puppet]) -> None:
    """Validation precedes mutation; immutable definitions store no execution fields."""
    stage, hero, _ = game
    hero.say("valid", seconds=10)
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
    assert {f.name for f in fields(_Say("text"))} == {"text", "seconds"}
    assert {f.name for f in fields(_Think("text"))} == {"text", "seconds"}
    assert fields(_ClearBubble()) == ()


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
    _step(stage)
    frame(stage)
    before = target.copy()
    stage.camera = (20, 0)
    _step(stage)
    frame(stage)
    assert target.get_at((220, 125)) == before.get_at((240, 125))
    hero.visible = False
    _step(stage)
    frame(stage)
    assert target.get_at((220, 125))[:3] == (0, 0, 128)
    hero.visible = True
    stage.camera = (0, 0)
    hero.scale = 2
    hero.direction = 0
    hero.rotation_style = RotationStyle.LEFT_RIGHT
    hero.costume = Costume(Image.new("RGBA", (40, 10), "orange"), anchor=(2, 3))
    _step(stage)
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

    _step(stage)
    frame(stage)
    assert target.get_at((240, 125))[:3] == (255, 0, 0)


def test_puppet_render_and_thought_connector(game: tuple[Stage, Sprite, Puppet]) -> None:
    """Puppet attachments define placement; thought and speech connectors differ."""
    stage, hero, puppet = game
    hero.visible = False
    puppet.position = (0, -100)
    puppet.say("hello")
    _step(stage)
    frame(stage)
    assert stage._target is not None
    speech = pygame.image.tobytes(stage._target, "RGBA")
    puppet.think("hello")
    _step(stage)
    frame(stage)
    assert pygame.image.tobytes(stage._target, "RGBA") != speech
    rest = puppet.pose
    puppet.pose = rest.with_angles({"right_elbow": 60})
    puppet.scale = 0.8
    puppet.direction = 120
    _step(stage)
    frame(stage)
    assert isinstance(puppet._bubble, _Think)


def test_layer_order_and_oversized_actor(game: tuple[Stage, Sprite, Puppet]) -> None:
    """Bubble order uses layers then insertion; huge actors fall back to viewport placement."""
    stage, hero, puppet = game
    puppet.visible = False
    second = Sprite(hero.costume)
    stage.add(second)
    hero.say("AAAAAAAA")
    second.say("BBBBBBBB")
    _step(stage)
    frame(stage)
    assert stage._target is not None
    first_order = pygame.image.tobytes(stage._target, "RGBA")
    hero.layer = 1
    _step(stage)
    frame(stage)
    assert pygame.image.tobytes(stage._target, "RGBA") != first_order
    hero.layer = 0
    _step(stage)
    frame(stage)
    assert pygame.image.tobytes(stage._target, "RGBA") == first_order
    hero.scale = 100
    pygame.font.init()
    font = pygame.font.Font(None, 24)
    layout = _layout(stage, hero, font, "huge actor")
    assert layout is not None
    body, _, _ = layout
    assert 8 <= body.top <= body.bottom <= stage.height - 8
    _step(stage)
    frame(stage)


def test_timed_replacement_identity_and_removal(game: tuple[Stage, Sprite, Puppet]) -> None:
    stage, hero, puppet = game
    old = hero.say("old", seconds=2)
    puppet.think("independent", seconds=1)
    _step(stage)
    request = hero._bubble
    assert isinstance(request, _BubbleRun)
    stage._tick = 15
    replacement = hero.think("new", seconds=1)
    _step(stage)
    assert old.cancelled
    _freeze(request, stage.time, cancel=True)
    assert isinstance(hero._bubble, _BubbleRun) and not replacement.done
    stage.remove(hero)
    assert replacement.cancelled and hero._bubble is None
    stage.add(hero)
    tick(stage, 61)
    assert hero._bubble is None and puppet._bubble is None


def test_pause_defers_clearing_and_hidden_time_continues(
    game: tuple[Stage, Sprite, Puppet],
) -> None:
    stage, hero, _ = game
    hero.say("timed", seconds=1)
    _step(stage)
    stage.pause()
    clearing = hero.clear_bubble()
    _step(stage)
    assert hero._bubble is not None and not clearing.done
    stage.resume()
    _step(stage)
    assert hero._bubble is None and clearing.done
    hero.visible = False
    action = hero.think("hidden", seconds=0.1)
    _step(stage)
    tick(stage, 6)
    assert action.done and hero._bubble is None


def test_blank_and_zero_duration(game: tuple[Stage, Sprite, Puppet]) -> None:
    stage, hero, _ = game
    empty = hero.say(" ", seconds=1)
    _step(stage)
    hero.say("new")
    _step(stage)
    tick(stage, 60)
    assert empty.done and isinstance(hero._bubble, _Say)
    hero.act(hero.sequence().say("zero", seconds=0).think("next"))
    _step(stage)
    assert isinstance(hero._bubble, _BubbleRun)
    tick(stage)
    assert isinstance(hero._bubble, _Think)
