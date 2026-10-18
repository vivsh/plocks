"""The first complete desktop path and its ownership/lifecycle invariants."""

from pathlib import Path
from shutil import copyfile

import pygame
import pytest
from PIL import Image

from plocks import (
    Canvas,
    Costume,
    Event,
    GamepadButton,
    GamepadPress,
    Key,
    Sound,
    Sprite,
    SpriteSheet,
    Stage,
    StageError,
    Voice,
)


def test_pillow_snapshot_and_bounds() -> None:
    """Caller edits and exported-image edits cannot mutate a costume."""
    source = Image.new("RGBA", (10, 20), "red")
    costume = Costume(source, anchor=(0, 0))
    source.putpixel((0, 0), (0, 0, 0, 0))
    exported = costume.to_pillow()
    assert exported.getpixel((0, 0)) == (255, 0, 0, 255)
    exported.putpixel((0, 0), (0, 0, 0, 0))
    assert costume.to_pillow().getpixel((0, 0)) == (255, 0, 0, 255)
    sprite = Sprite(costume, x=5, y=6)
    assert sprite.bounds.left == 5
    assert sprite.bounds.top == 6
    sprite.direction += 90
    assert sprite.bounds.width == pytest.approx(20)
    assert sprite.bounds.height == pytest.approx(10)


def test_desktop_input_sound_render_cleanup() -> None:
    """A native event starts OGG playback and updates/draws before complete cleanup."""
    stage = Stage(background="navy")
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    sprite = Sprite(Image.new("RGBA", (12, 12), "orange"))
    stage.add(sprite)
    sound = Sound(Path(__file__).parents[1] / "tests/fixtures/games/proof/assets/tone.ogg")
    voices: list[Voice] = []
    canvases: list[Canvas] = []

    @stage.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])
    def pressed(event: Event[Stage, GamepadPress]) -> None:
        voices.append(stage.play(sound))
        assert not voices[-1].finished

    @stage.on_update
    def update(event: Event[Stage, float]) -> None:
        dt = event.data
        sprite.x += 100 * dt
        if stage.time <= dt:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        if stage.time >= 0.1:
            stage.stop()

    @stage.on_draw
    def draw(canvas: Canvas) -> None:
        canvas.text("proof", (0, 0))
        canvases.append(canvas)

    assert pygame.display.get_surface() is None
    stage.run()
    assert sprite.x == pytest.approx(100 * 7 / 60)
    assert len(voices) == 1
    assert voices[0].finished
    assert pygame.display.get_surface() is None
    assert pygame.mixer.get_init() is None
    with pytest.raises(StageError):
        stage.run()
    with pytest.raises(StageError):
        canvases[0].text("expired", (0, 0))


def test_callback_traceback_survives_cleanup() -> None:
    """A game exception remains its original type and always closes native resources."""
    stage = Stage()
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)

    @stage.on_update
    def update(event: Event[Stage, float]) -> None:
        raise LookupError("game failure")

    with pytest.raises(LookupError, match="game failure"):
        stage.run()
    assert not stage.running
    assert pygame.display.get_surface() is None


def test_image_and_sound_paths_resolve_from_working_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All file-based asset constructors use cwd without creating a display or audio device."""
    source = Path(__file__).parents[1] / "tests/fixtures/games/proof/assets"
    assets = tmp_path / "assets"
    assets.mkdir()
    copyfile(source / "tone.ogg", assets / "tone.ogg")
    picture = Path(__file__).parents[1] / "src/plocks/_games/platformer/assets/hero.png"
    copyfile(picture, assets / "hero.png")
    monkeypatch.chdir(tmp_path)
    costume = Costume("assets/hero.png")
    sprite = Sprite("assets/hero.png")
    sheet = SpriteSheet("assets/hero.png", frame_size=(costume.width, costume.height))
    sound = Sound("assets/tone.ogg")
    assert sprite.costume.width == costume.width
    assert sheet.frame(row=0, column=0).height == costume.height
    assert sound._encoded == (assets / "tone.ogg").read_bytes()
    assert Path.cwd() == tmp_path
    assert not pygame.display.get_init() and not pygame.mixer.get_init()
