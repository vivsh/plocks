"""Dataclass game values belong directly to each actor or Stage."""

from collections.abc import Callable, Iterator
from dataclasses import FrozenInstanceError, dataclass, field
from pathlib import Path
from typing import cast

import pytest

from plocks import Event, Joint, Key, Message, Puppet, Script, Skeleton, Sprite, Stage, StageError
from plocks._runtime import close, dispatch
from tests.test_scripts import ticks

IMAGE = Path(__file__).parent / "fixtures/games/state_proof/assets/hero.png"


@dataclass
class PlayerState:
    health: int = 100
    speed: float = 1
    alive: bool = True
    hits: list[int] = field(default_factory=list[int])


@dataclass
class GameState:
    score: int = 0


@pytest.fixture
def world() -> Iterator[tuple[Stage[GameState], Sprite[PlayerState], Sprite[PlayerState]]]:
    stage = Stage(state=GameState)
    first, second = Sprite(IMAGE, state=PlayerState), Sprite(IMAGE, state=PlayerState)
    stage.add(first)
    stage.add(second)
    stage._state = "running"
    yield stage, first, second
    close(stage)


def test_each_owner_constructs_an_independent_dataclass() -> None:
    """Reusing a class shares neither the root state nor default-factory collections."""
    first, second = Sprite(IMAGE, state=PlayerState), Sprite(IMAGE, state=PlayerState)
    person = Puppet(Skeleton({"root": Joint(None)}), parts={"root": IMAGE}, state=PlayerState)
    stage, other = Stage(state=GameState), Stage(state=GameState)
    assert type(first.state) is PlayerState and type(person.state) is PlayerState
    assert first.state is not second.state and first.state is not person.state
    first.state.health = 7
    first.state.hits.append(10)
    stage.state.score = 11
    assert second.state.health == person.state.health == 100
    assert second.state.hits == person.state.hits == []
    assert first.state.hits is not second.state.hits and second.state.hits is not person.state.hits
    assert other.state.score == 0 and stage.state is not other.state
    assert vars(first.state) == {"health": 7, "speed": 1, "alive": True, "hits": [10]}
    assert not hasattr(first.state, "_values")


@pytest.mark.parametrize("kind", ["sprite", "puppet", "stage"])
def test_float_annotation_accepts_integer_default_and_decimal_assignment(kind: str) -> None:
    """Float annotations do not turn an integer default into an integer-only runtime field."""
    owner: Sprite[PlayerState] | Puppet[PlayerState] | Stage[PlayerState]
    if kind == "sprite":
        owner = Sprite(IMAGE, state=PlayerState)
    elif kind == "puppet":
        owner = Puppet(Skeleton({"root": Joint(None)}), parts={"root": IMAGE}, state=PlayerState)
    else:
        owner = Stage(state=PlayerState)
    assert owner.state.speed == 1 and type(owner.state.speed) is int
    owner.state.speed = 0.5
    owner.state.speed += 0.25
    assert owner.state.speed == 0.75 and type(owner.state.speed) is float
    # Python float fields retain ordinary Python behavior, without engine validation.
    owner.state.speed = float("inf")
    assert owner.state.speed == float("inf")


def test_unconfigured_and_explicit_none_state() -> None:
    """Owners without a schema do not allocate an empty state wrapper or value table."""
    for owner in (
        Sprite(IMAGE),
        Sprite(IMAGE, state=None),
        Puppet.stick_figure(),
        Puppet(Skeleton({"root": Joint(None)}), parts={"root": IMAGE}, state=None),
        Stage(),
        Stage(state=None),
    ):
        assert owner.state is None


def test_state_association_is_read_only() -> None:
    """Ordinary fields are writable while the owner always retains its constructed instance."""
    for owner in (
        Sprite(IMAGE, state=PlayerState),
        Puppet(Skeleton({"root": Joint(None)}), parts={"root": IMAGE}, state=PlayerState),
        Stage(state=PlayerState),
    ):
        original = owner.state
        with pytest.raises(AttributeError):
            setattr(owner, "state", PlayerState())  # noqa: B010 -- verify the public property boundary
        assert owner.state is original
        owner.state.health -= 1
        assert original.health == 99


def test_supplied_instances_and_non_dataclass_classes_are_rejected() -> None:
    """Constructors accept a dataclass class, preserving one fresh instance per owner."""
    factories: tuple[Callable[[type[object]], object], ...] = (
        lambda schema: Sprite(IMAGE, state=schema),
        lambda schema: Puppet(Skeleton({"root": Joint(None)}), parts={"root": IMAGE}, state=schema),
        lambda schema: Stage(state=schema),
    )
    for invalid in (PlayerState(), object(), object, int, dict):
        for factory in factories:
            with pytest.raises(TypeError, match="dataclass class"):
                factory(cast(type[object], invalid))


def test_normal_constructors_run_once_and_exceptions_are_preserved() -> None:
    """User initialization is called normally, without engine wrappers or translated failures."""
    calls: list[object] = []

    @dataclass
    class Initialized:
        health: int = 100

        def __post_init__(self) -> None:
            self.health = 50
            calls.append(self)

    owners: tuple[Sprite[Initialized] | Puppet[Initialized] | Stage[Initialized], ...] = (
        Sprite(IMAGE, state=Initialized),
        Puppet(Skeleton({"root": Joint(None)}), parts={"root": IMAGE}, state=Initialized),
        Stage(state=Initialized),
    )
    assert len(calls) == 3
    assert all(owner.state is value for owner, value in zip(owners, calls))
    assert all(owner.state.health == 50 for owner in owners)

    @dataclass
    class Required:
        value: int

    with pytest.raises(TypeError, match="value"):
        Stage(state=Required)
    error = LookupError("from dataclass initialization")

    @dataclass
    class Failing:
        def __post_init__(self) -> None:
            raise error

    with pytest.raises(LookupError) as caught:
        Sprite(IMAGE, state=Failing)
    assert caught.value is error


def test_slotted_inherited_and_frozen_dataclasses_keep_normal_behavior() -> None:
    """Standard dataclass layouts and user methods need no Plocks descriptors or base class."""

    @dataclass(slots=True)
    class Base:
        health: int = 100

    @dataclass(slots=True)
    class Extended(Base):
        coins: list[int] = field(default_factory=list[int])

        def heal(self) -> None:
            self.health += 5

    hero = Sprite(IMAGE, state=Extended)
    hero.state.heal()
    hero.state.coins.append(7)
    assert hero.state.health == 105 and hero.state.coins == [7]
    assert not hasattr(hero.state, "__dict__")

    @dataclass(frozen=True)
    class ReadOnly:
        name: str = "visitor"

    stage = Stage(state=ReadOnly)
    assert stage.state.name == "visitor"
    with pytest.raises(FrozenInstanceError):
        setattr(stage.state, "name", "changed")  # noqa: B010 -- ordinary frozen dataclass behavior


def test_plain_dataclass_assignments_have_no_runtime_interception() -> None:
    """Untyped assignments follow Python rules; the engine does not provide a second validator."""
    hero = Sprite(IMAGE, state=PlayerState)
    setattr(hero.state, "health", "untyped input")  # noqa: B010 -- deliberately bypass static checking
    assert vars(hero.state)["health"] == "untyped input"
    hero.state.health = 30
    assert hero.state.health == 30


def test_shared_script_broadcasts_to_normal_typed_state_handlers(
    world: tuple[Stage[GameState], Sprite[PlayerState], Sprite[PlayerState]],
) -> None:
    """Scripts share definitions; handlers update their own dataclass and the same Stage score."""
    stage, first, second = world
    second.state.health = 20
    damage = Message[int]("damage")

    @first.on_broadcast(damage)
    @second.on_broadcast(damage)
    def hurt(event: Event[Sprite[PlayerState], int]) -> None:
        actor = event.target
        if event.source is not actor:
            return
        actor.state.health -= event.data
        actor.state.alive = actor.state.health > 10
        actor.state.hits.append(event.data)
        stage.state.score += 1

    recipe = Script().wait(0.1).broadcast(damage, 10, wait=True).glide_by(x=10, seconds=0.1)
    one, two = first.act(recipe), second.act(recipe)
    ticks(stage, 3)
    assert (first.state.health, second.state.health, stage.state.score) == (100, 20, 0)
    ticks(stage, 20)
    assert one.done and two.done
    assert (first.state.health, second.state.health, stage.state.score) == (90, 10, 2)
    assert first.state.alive and not second.state.alive
    assert first.state.hits == second.state.hits == [10]
    assert first.x == second.x == 10


def test_paused_input_updates_state_while_script_waits_and_cancellation_stops_delivery(
    world: tuple[Stage[GameState], Sprite[PlayerState], Sprite[PlayerState]],
) -> None:
    """Pause stops scheduled work but ordinary UI handlers retain direct field access."""
    stage, first, _ = world
    damage = Message[int]("damage")

    @first.on_broadcast(damage)
    def hurt(event: Event[Sprite[PlayerState], int]) -> None:
        event.target.state.health -= event.data

    @first.on_key_down(Key.H)
    def hit(event: Event[Sprite[PlayerState], Key]) -> None:
        event.target.state.health -= 1

    action = first.act(Script().wait(0.1).broadcast(damage, 10, to=first))
    ticks(stage, 2)
    stage.pause()
    stage._pending.append(Key.H)
    dispatch(stage)
    ticks(stage, 20)
    assert first.state.health == 99 and not action.done
    stage.resume()
    ticks(stage, 12)
    assert first.state.health == 89 and action.done
    canceled = first.act(Script().wait(0.1).broadcast(damage, 50, to=first))
    canceled.cancel()
    ticks(stage, 20)
    assert first.state.health == 89


def test_detach_readd_and_close_preserve_the_same_state(
    world: tuple[Stage[GameState], Sprite[PlayerState], Sprite[PlayerState]],
) -> None:
    """Engine resource cleanup never resets or releases caller-visible authored values."""
    stage, first, _ = world
    state = first.state
    first.state.health = 25
    stage.state.score = 7
    action = first.glide_by(x=50, seconds=1)
    ticks(stage, 2)
    stage.remove(first)
    assert action.cancelled and first.state is state and state.health == 25
    stage.add(first)
    assert first.state is state
    close(stage)
    close(stage)
    assert first.state is state and state.health == 25 and stage.state.score == 7
    first.state.health += 1
    with pytest.raises(StageError):
        first.wait(0.1)
    assert not stage._actions and not stage.objects


def test_callback_failures_keep_original_exception_and_already_written_values(
    world: tuple[Stage[GameState], Sprite[PlayerState], Sprite[PlayerState]],
) -> None:
    """Ordinary Python writes are not rolled back when a handler fails and cleanup runs."""
    stage, first, _ = world
    message = Message[int]("failing handler")
    error = LookupError("deliberate dataclass handler failure")

    @first.on_broadcast(message)
    def fail(event: Event[Sprite[PlayerState], int]) -> None:
        event.target.state.health -= event.data
        raise error

    first.broadcast(message, 3, to=first)
    with pytest.raises(LookupError) as caught:
        ticks(stage, 3)
    assert caught.value is error
    close(stage)
    assert first.state.health == 97 and not stage._actions and not stage._messages


def test_puppet_and_stage_events_preserve_their_dataclass_state_types() -> None:
    """Every receiver kind uses its constructed state directly in typed callbacks."""
    stage = Stage(state=GameState)
    person = Puppet(Skeleton({"root": Joint(None)}), parts={"root": IMAGE}, state=PlayerState)
    stage.add(person)
    stage._state = "running"
    message = Message[int]("health")

    @person.on_broadcast(message)
    def health(event: Event[Puppet[PlayerState], int]) -> None:
        event.target.state.health += event.data

    @stage.on_key_down(Key.H)
    def score(event: Event[Stage[GameState], Key]) -> None:
        event.target.state.score += 3

    try:
        stage._pending.append(Key.H)
        dispatch(stage)
        stage.broadcast(message, -10, to=person)
        ticks(stage, 3)
        assert person.state.health == 90 and stage.state.score == 3
    finally:
        close(stage)


def test_custom_state_operations_and_conditions_are_removed() -> None:
    """The public and internal API expose no compatibility state descriptors or operations."""
    import plocks
    from plocks import _commands, conditions, state

    removed = (
        "Field",
        "State",
        "StateEquals",
        "StateLessThan",
        "StageStateEquals",
        "StageStateLessThan",
    )
    assert not any(hasattr(plocks, name) for name in removed)
    assert not hasattr(state, "Field") and not hasattr(state, "State")
    assert not any(hasattr(conditions, name) for name in removed[2:])
    for name in ("set_state", "change_state", "set_stage_state", "change_stage_state"):
        assert not hasattr(Script, name)
    for name in ("_SetState", "_ChangeState", "_SetStageState", "_ChangeStageState"):
        assert not hasattr(_commands, name)
