"""A normal local Stage receives a shared view and supplies logical controls."""

from __future__ import annotations

import pygame

from ._network import _Client, _client, _JoinConfig
from .canvas import Canvas
from .errors import NetworkError
from .stage import Stage


def join(config: _JoinConfig) -> None:
    """Run one observed session; errors reach the CLI rather than a hidden task."""
    stage = Stage(width=640, height=480, gamepad_count=1)
    try:
        stage._network = _client(config)

        @stage.on_draw
        def display(canvas: Canvas) -> None:
            owner = stage._network
            if not isinstance(owner, _Client) or owner.frame is None:
                text = (
                    "Release controls to join..."
                    if isinstance(owner, _Client) and owner.control.phase == "neutral"
                    else "Connecting to the game..."
                )
                canvas.text(text, (-280, 20), size=24)
                canvas.text("WASD + Space/F, or your controller", (-280, -15), size=20)
                return
            target = stage._target
            assert target is not None
            width, height = owner.frame.get_size()
            factor = min(stage.width / width, (stage.height - 32) / height)
            size = max(1, round(width * factor)), max(1, round(height * factor))
            picture = pygame.transform.scale(owner.frame, size)
            target.blit(picture, ((stage.width - size[0]) // 2, 0))

        stage.run()
    except (OSError, NetworkError) as error:
        raise NetworkError(f"Cannot play with {config.address}:{config.port}: {error}") from error
    finally:
        if stage._network is not None:
            from ._network import close

            close(stage)


def configuration(address: str, port: int, player: int, code: str) -> _JoinConfig:
    """Validate user-facing one-based numbering without opening a connection."""
    from ipaddress import ip_address

    ip_address(address)
    if type(player) is not int or player < 1:
        raise ValueError("player must be a positive player number (1, 2, ...)")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("port must be in 1..65535")
    if not code.strip() or len(code) > 128:
        raise ValueError("Enter the host's connection code")
    return _JoinConfig(address, port, player - 1, code.strip())
