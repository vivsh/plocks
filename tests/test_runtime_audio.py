"""Input edges, lifecycle recovery, bounded scheduling, and sound occurrence safety."""

import asyncio
from pathlib import Path

import pygame
import pytest

from plocks import AudioError, Bounds, Event, Key, Sound, Stage, StageError
from plocks._runtime import advance, close, dispatch, drive, poll


def test_fixed_steps_and_bounded_backlog() -> None:
    """A stalled frame advances at most five ticks and discards whole-step excess."""
    stage = Stage()
    stage._state = "running"
    times: list[float] = []

    @stage.on_update
    def record(event: Event[Stage, float]) -> None:
        times.append(event.data)

    advance(stage, 10)
    advance(stage, 20)
    assert len(times) == 5 and all(dt == 1 / 60 for dt in times)
    assert stage.time == 5 / 60
    assert 0 <= stage._accumulator < 1 / 60


def test_pause_sources_and_resume_baseline() -> None:
    """Automatic resume cannot remove user pause or consume paused wall time."""
    stage = Stage()
    stage._state = "running"
    advance(stage, 0)
    advance(stage, 0.05)
    before = stage.time
    stage.pause()
    stage._set_pause("application", True)
    stage._set_pause("application", False)
    advance(stage, 100)
    assert stage.paused and stage.time == before
    stage.resume()
    advance(stage, 200)
    assert stage.time == before
    advance(stage, 200 + 1 / 60)
    assert stage.time == pytest.approx(before + 1 / 60)


def test_input_edges_repeat_and_focus_clear() -> None:
    """Repeated keydown is one edge; independent hide/focus reasons do not cancel each other."""
    stage = Stage()
    stage._state = "running"
    stage._target = pygame.display.set_mode((10, 10))
    pygame.event.clear()
    presses: list[int] = []
    stage.on_key_down(Key.SPACE)(lambda event: presses.append(1))
    for _ in range(2):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    poll(stage)
    dispatch(stage)
    dispatch(stage)
    assert presses == [1] and stage.keyboard.is_down(Key.SPACE)
    pygame.event.post(pygame.event.Event(pygame.WINDOWFOCUSLOST))
    pygame.event.post(pygame.event.Event(pygame.WINDOWHIDDEN))
    pygame.event.post(pygame.event.Event(pygame.WINDOWSHOWN))
    poll(stage)
    assert stage.paused and not stage.keyboard.is_down(Key.SPACE)
    pygame.event.post(pygame.event.Event(pygame.WINDOWFOCUSGAINED))
    poll(stage)
    assert not stage.paused
    close(stage)


def test_snapshot_callback_registration() -> None:
    """A callback registered during dispatch joins only a subsequent dispatch of that list."""
    stage = Stage()
    stage._state = "running"
    calls: list[str] = []

    def later(event: Event[Stage, Key]) -> None:
        calls.append("later")

    @stage.on_key_down(Key.A)
    def first(event: Event[Stage, Key]) -> None:
        calls.append("first")
        stage.on_key_down(Key.A)(later)

    stage._pending.append(Key.A)
    dispatch(stage)
    assert calls == ["first"]
    stage._pending.append(Key.A)
    dispatch(stage)
    assert calls == ["first", "first", "later"]


def test_existing_resources_are_not_closed_on_rejection() -> None:
    """Refusing a second display leaves the original caller-owned display alive."""
    target = pygame.display.set_mode((10, 10))
    with pytest.raises(StageError):
        Stage().run()
    assert pygame.display.get_surface() is target


def test_cancelled_driver_releases_resources() -> None:
    """Cancellation has the same cleanup guarantees as normal closure and callback failure."""
    stage = Stage()
    stage._state = "running"
    stage._target = pygame.display.set_mode((10, 10))

    async def cancel() -> None:
        task = asyncio.create_task(drive(stage))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel())
    assert not stage.running and stage._target is None
    assert pygame.display.get_surface() is None


def test_sound_overlap_limit_stale_handle_and_master_volume() -> None:
    """Playback does not steal channels, and a retired handle cannot stop its replacement."""
    sound = Sound(Path(__file__).parents[1] / "tests/fixtures/games/proof/assets/tone.ogg")
    stage = Stage()
    stage._state = "running"
    voices = [stage.play(sound, volume=0.3, loop=True) for _ in range(16)]
    with pytest.raises(AudioError):
        stage.play(sound)
    previous = voices[0]
    previous.stop()
    replacement = stage.play(sound, volume=0.3, loop=True)
    previous.stop()
    assert previous.finished and not replacement.finished
    stage.volume = 0.5
    assert replacement._channel is not None
    assert replacement._channel.get_volume() == pytest.approx(0.5)
    assert replacement._sample is not None
    assert replacement._sample.get_volume() == pytest.approx(0.3, abs=1 / 128)
    stage.pause()
    assert not replacement.finished
    stage.stop_sounds()
    assert replacement.finished and all(voice.finished for voice in voices)


def test_sound_snapshot_survives_source_removal(tmp_path: Path) -> None:
    """Playback reads the immutable snapshot, not a mutable or missing source file."""
    filename = tmp_path / "tone.ogg"
    filename.write_bytes(
        (Path(__file__).parents[1] / "tests/fixtures/games/proof/assets/tone.ogg").read_bytes()
    )
    sound = Sound(filename)
    filename.unlink()
    stage = Stage()
    with pytest.raises(StageError):
        stage.play(sound)
    stage._state = "running"
    assert not stage.play(sound).finished
    stage.stop_sounds()


def test_coordinate_roundtrip_and_validation() -> None:
    """Camera conversions round-trip without storing synchronized bounds or positions."""
    stage = Stage()
    stage.camera = (100, -50)
    assert stage.from_screen(stage.to_screen((12, 34))) == (12, 34)
    assert stage.from_screen(stage.to_screen((12, 34), world=False), world=False) == (12, 34)
    assert stage.world_bounds.center == stage.camera
    with pytest.raises(ValueError):
        stage.camera = (float("nan"), 0)
    with pytest.raises(ValueError):
        stage.volume = 1.1
    with pytest.raises(ValueError):
        Bounds(1, 2, -1, 3)
