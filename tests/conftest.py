"""Keep native resources isolated; select dummy drivers in automated test commands."""

from collections.abc import Iterator

import pygame
import pytest


@pytest.fixture(autouse=True)
def release_native_resources() -> Iterator[None]:
    """A failing case must not leave display/audio resources affecting another case."""
    yield
    pygame.mixer.quit()
    pygame.font.quit()
    pygame.display.quit()
