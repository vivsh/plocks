"""Scripts, timing, ownership and message delivery through the synchronous API."""

from collections.abc import Iterator
from dataclasses import fields

import pytest
from PIL import Image

from plocks import (
    Action,
    CostumeSource,
    Event,
    Message,
    Puppet,
    Script,
    Sprite,
    Stage,
    StageError,
)
from plocks._operations import _BubbleRun
from plocks._runtime import close, dispatch
from plocks._scripts import _deliver, _sample, _step


@pytest.fixture
def game() -> Iterator[tuple[Stage, Sprite]]:
    stage = Stage()
    actor = Sprite(Image.new("RGBA", (8, 8), "red"))
    stage.add(actor)
    stage._state = "running"
    yield stage, actor
    close(stage)


def ticks(stage: Stage, count: int) -> None:
    for _ in range(count):
        _deliver(stage)
        dispatch(stage)
        if not stage.paused:
            _step(stage)
            stage._tick += 1
            _sample(stage)


def test_script_snapshot_repetition_and_fractional_time(game: tuple[Stage, Sprite]) -> None:
    stage, hero = game
    recipe = Script(Sprite).repeat(7).glide_by(x=1, seconds=1 / 7)
    action = hero.act(recipe)
    recipe.move(100)
    assert hero.x == 0
    ticks(stage, 61)
    assert action.done and hero.x == 7
    second = hero.act(Script(Sprite).move(5))
    _step(stage)
    assert second.done and hero.x == 12
    assert set(recipe.__slots__) == {"_target_type", "_times", "_commands"}
    assert fields(action._state)


def test_script_reuse_and_empty_loop_rejected(game: tuple[Stage, Sprite]) -> None:
    stage, hero = game
    friend = Sprite(hero.costume)
    stage.add(friend)
    shared = Script().wait(1)
    first = friend.act(shared)
    second = hero.act(shared)
    assert first is not second
    first.cancel()
    second.cancel()
    with pytest.raises(ValueError, match="contain commands"):
        hero.act(Script(Sprite).repeat())
    for count in (-1, True):
        with pytest.raises((TypeError, ValueError)):
            Script(Sprite).repeat(count)
    zero = hero.act(Script(Sprite).repeat(0).move(99))
    _step(stage)
    assert zero.done and hero.x == 0


def test_during_cancels_visual_background_and_sibling_conflicts(game: tuple[Stage, Sprite]) -> None:
    stage, hero = game
    frames: list[CostumeSource] = [hero.costume, Image.new("RGBA", (8, 8), "blue")]
    action = hero.act(
        Script(Sprite).during(
            Script(Sprite).glide_by(x=60, seconds=1),
            meanwhile=Script(Sprite).repeat().costumes(frames, fps=7),
        )
    )
    ticks(stage, 61)
    assert action.done and hero.x == 60 and not stage._actions
    hero.act(
        Script(Sprite).during(
            Script(Sprite).glide_by(x=1, seconds=1),
            meanwhile=Script(Sprite).glide_by(x=2, seconds=1),
        )
    )
    with pytest.raises(StageError, match="same property"):
        _step(stage)
    assert not stage._actions


def test_calls_returning_none_release_admissions(game: tuple[Stage, Sprite]) -> None:
    stage, hero = game

    event = Message[None]("launch")

    @hero.on_broadcast(event)
    def launch(occurrence: Event[Sprite, None]) -> None:
        hero.glide_by(x=60, seconds=1)

    outer = hero.broadcast(event, wait=True)
    ticks(stage, 3)
    assert outer.done
    ticks(stage, 62)
    assert hero.x == 60


def test_calls_returning_action_own_new_work(game: tuple[Stage, Sprite]) -> None:
    stage, hero = game

    event = Message[None]("launch")

    @hero.on_broadcast(event)
    def launch(occurrence: Event[Sprite, None]) -> Action:
        hero.glide_by(x=100, seconds=10)
        return hero.wait(0.1)

    outer = hero.broadcast(event, wait=True)
    ticks(stage, 10)
    assert outer.done and not stage._actions
    assert 0 < hero.x < 10
    frozen = hero.x
    ticks(stage, 20)
    assert hero.x == frozen


def test_join_borrows_inputs_and_cancels_on_input_cancellation(game: tuple[Stage, Sprite]) -> None:
    stage, hero = game
    first = hero.glide_by(x=30, seconds=1)
    second = hero.glide_by(y=30, seconds=1)
    joined = stage.join(first, second)
    joined.cancel()
    assert not first.done and not second.done
    another = stage.join(first, second)
    first.cancel()
    ticks(stage, 1)
    assert another.cancelled and not second.done


def test_loop_fairness_zero_glide_and_shared_snapshot(game: tuple[Stage, Sprite]) -> None:
    stage, hero = game
    action = hero.act(Script(Sprite).repeat().move(1))
    ticks(stage, 10)
    assert hero.x == 10
    action.cancel()
    zero = hero.act(Script(Sprite).glide_to(x=100, seconds=0).move(1))
    _step(stage)
    assert hero.x == 100 and not zero.done
    ticks(stage, 2)
    assert hero.x == 101 and zero.done


def test_message_payload_join_and_busy(game: tuple[Stage, Sprite]) -> None:
    stage, hero = game
    message = Message[int]("steps")
    seen: list[int] = []

    @hero.on_broadcast(message)
    def receive(event: Event[Sprite, int]) -> Action:
        amount = event.data
        seen.append(amount)
        return hero.glide_by(x=amount, seconds=0.2)

    first = stage.broadcast(message, 12, wait=True)
    ticks(stage, 3)
    ignored = stage.broadcast(message, 99, wait=True)
    ticks(stage, 3)
    assert seen == [12] and ignored.done and not first.done
    ticks(stage, 20)
    assert hero.x == 12 and first.done and not stage._actions


def test_bubble_replacement_cancels_owner_identity_safe(game: tuple[Stage, Sprite]) -> None:
    stage, hero = game
    old = hero.act(
        Script(Sprite).during(
            Script(Sprite).glide_by(x=60, seconds=1), meanwhile=Script(Sprite).say("old", seconds=2)
        )
    )
    ticks(stage, 15)
    assert isinstance(hero._bubble, _BubbleRun)
    replacement = hero.say("new", seconds=1)
    _step(stage)
    assert old.cancelled and not replacement.done
    frozen = hero.x
    ticks(stage, 65)
    assert hero._bubble is None and hero.x == frozen


def test_puppet_pose_and_part_commands(game: tuple[Stage, Sprite]) -> None:
    stage, _ = game
    person = Puppet.stick_figure()
    stage.add(person)
    rest = person.pose
    bent = rest.with_angles({"right_elbow": 60})
    action = person.poses((rest, bent), fps=2)
    ticks(stage, 15)
    assert person.pose.angles["right_elbow"] == pytest.approx(30)
    part = next(iter(person.parts))
    person.set_part_costume(part, Image.new("RGBA", (5, 5)))
    ticks(stage, 20)
    assert action.done and person.parts[part].width == 5


def test_sprite_helpers_create_unbound_independent_recipes(game: tuple[Stage, Sprite]) -> None:
    stage, hero = game
    author = Sprite(hero.costume)
    friend = Sprite(hero.costume, x=100)
    stage.add(friend)
    recipe = author.repeat(2).glide_by(x=12, seconds=0.1)
    assert author._stage is None and not stage._actions
    first = hero.act(recipe)
    second = friend.act(recipe)
    ticks(stage, 4)
    first.cancel()
    frozen = hero.x
    ticks(stage, 20)
    assert second.done and friend.x == 124
    assert hero.x == frozen and author.x == 0
    appearance = author.sequence().set_costume(friend.costume)
    assert hero.act(appearance) is not first


def test_puppet_helpers_keep_pose_capabilities_without_stage_membership(
    game: tuple[Stage, Sprite],
) -> None:
    stage, _ = game
    person = Puppet.stick_figure()
    rest = person.pose
    recipe = person.sequence().set_pose(rest).move(3)
    assert person._stage is None and not stage._actions
    stage.add(person)
    action = person.act(recipe)
    ticks(stage, 1)
    assert action.done and person.x == 3
    repeated = person.repeat(2).move(4)
    person.act(repeated)
    ticks(stage, 3)
    assert person.x == 11
    with pytest.raises(ValueError, match="contain commands"):
        person.act(person.repeat())
