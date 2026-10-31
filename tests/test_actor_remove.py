"""Actor removal uses stage cleanup, including self-removal from clone handlers."""

import pytest

from plocks import Event, Image, PhysicsError, Puppet, Sprite, Stage
from plocks._runtime import close
from plocks._scripts import _step


@pytest.mark.parametrize("puppet", [False, True])
def test_remove_is_idempotent_and_releases_physics(puppet: bool) -> None:
    stage = Stage(physics=True)
    actor = Puppet.stick_figure() if puppet else Sprite(Image.rectangle(20, 20))
    actor.remove()
    stage.add(actor)
    body = actor.body
    actor.say("hello")
    actor.remove()
    actor.remove()
    assert actor not in stage.objects and actor._stage is None
    assert actor._bubble is None
    with pytest.raises(PhysicsError):
        _ = body.shape
    stage.add(actor)
    assert actor.body is not body
    close(stage)


def test_clone_handler_can_remove_receiver_without_stage() -> None:
    stage = Stage()
    actor = Sprite(Image.rectangle(10, 10))
    stage.add(actor)

    @actor.on_clone
    def born(event: Event[Sprite, None]) -> None:
        event.target.remove()

    clone = actor.clone()
    stage._state = "running"
    try:
        from plocks._runtime import dispatch

        dispatch(stage)
        _step(stage)
        assert clone not in stage.objects and actor in stage.objects
        assert all(handler.actor is not clone for handler in stage._clone_handlers)
        replacement = actor.clone()
        dispatch(stage)
        assert replacement._stage is None and actor._stage is stage
        assert actor in stage.objects
    finally:
        close(stage)


@pytest.mark.parametrize("physics", [False, True])
@pytest.mark.parametrize("puppet", [False, True])
@pytest.mark.parametrize("running", [False, True])
def test_source_can_clone_again_after_repeated_clone_removal(
    physics: bool, puppet: bool, running: bool
) -> None:
    """Removing a copy never clears the source association needed for later clones."""
    stage = Stage(physics=physics)
    original = Puppet.stick_figure() if puppet else Sprite(Image.rectangle(10, 20))
    stage.add(original)
    if running:
        stage._state = "running"
    try:
        for _ in range(20):
            clone = original.clone()
            clone.remove()
            assert original._stage is stage and original in stage.objects
        replacement = original.clone()
        assert replacement is not original and replacement._stage is stage
    finally:
        close(stage)
