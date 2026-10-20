"""Report local frame and per-occurrence sound decode costs, without optimizing state."""

import json
import platform
import statistics
import time
from pathlib import Path

import pygame
from PIL import Image as PillowImage

from plocks import (
    Event,
    HumanJoint,
    Image,
    Message,
    Puppet,
    Script,
    Sound,
    Sprite,
    Stage,
    TileMap,
)
from plocks._render import frame
from plocks._runtime import close
from plocks._scripts import _count, _deliver, _sample, _step


def main() -> None:
    """Measure 100 sprites, 20 moving/posing Puppets, messages, and a culled tile world."""
    stage = Stage(640, 400)
    stage._target = pygame.display.set_mode((640, 400))
    stage._state = "running"
    image = Image(PillowImage.new("RGBA", (32, 32), "orange"))
    stage.add(TileMap(["#" * 100] * 100, {"#": image}, tile_size=(32, 32), x=-320, y=200))
    for index in range(100):
        stage.add(
            Sprite(
                image, x=(index % 20) * 30 - 300, y=(index // 20) * 50 - 100, direction=index * 7
            )
        )
    for index in range(20):
        person = Puppet.stick_figure()
        person.x = index * 30 - 300
        person.scale = 0.5
        stage.add(person)
        rest = person.skeleton.rest_pose()
        raised = rest.with_angles({HumanJoint.RIGHT_ELBOW: 90})
        person.act(
            Script(Puppet).during(
                Script(Puppet).repeat().glide_by(y=10, seconds=0.5).glide_by(y=-10, seconds=0.5),
                meanwhile=Script(Puppet).repeat().poses((rest, raised, rest), fps=2),
            )
        )
    delivered = 0
    message = Message[int]("benchmark")

    @stage.on_broadcast(message)
    def receive(event: Event[Stage, int]) -> None:
        nonlocal delivered
        delivered += event.data

    _step(stage)
    for _ in range(10):
        frame(stage)
    samples: list[float] = []
    messages: list[float] = []
    for _ in range(100):
        started = time.perf_counter()
        for _ in range(32):
            stage.broadcast(message, 1)
        _step(stage)
        _deliver(stage)
        _step(stage)
        messages.append(1000 * (time.perf_counter() - started))
        stage._tick += 1
        _sample(stage)
        _step(stage)
        frame(stage)
        samples.append(1000 * (time.perf_counter() - started))
    sound = Sound(Path(__file__).parents[1] / "tests/fixtures/games/proof/assets/tone.ogg")
    stage.play(sound).stop()  # device initialization excluded from repeated decode measurement
    audio: list[float] = []
    for _ in range(30):
        started = time.perf_counter()
        stage.play(sound).stop()
        audio.append(1000 * (time.perf_counter() - started))
    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "display": pygame.display.get_driver(),
                "pygame": pygame.version.ver,
                "frames": len(samples),
                "roots": len(stage._actions),
                "fibers": _count(stage),
                "message_deliveries": delivered,
                "message_batch_median_ms": statistics.median(messages),
                "frame_median_ms": statistics.median(samples),
                "frame_p95_ms": sorted(samples)[94],
                "audio_median_ms": statistics.median(audio),
                "audio_max_ms": max(audio),
            },
            indent=2,
        )
    )
    close(stage)


if __name__ == "__main__":
    main()
