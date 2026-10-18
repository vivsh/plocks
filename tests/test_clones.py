"""Scratch-style copies retain independent actor, handler and physics ownership."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import patch

import pygame
import pytest

from plocks import (
    BodyType,
    Click,
    Costume,
    Event,
    GamepadButton,
    GamepadPress,
    Joint,
    Key,
    Message,
    MouseButton,
    Puppet,
    RotationStyle,
    Script,
    Skeleton,
    Sprite,
    Stage,
    StageError,
    WhenBusy,
)
from plocks._runtime import _clear_input, advance, close
from plocks._scripts import _step, _trigger

IMAGE = Path(__file__).parent / "fixtures/games/state_proof/assets/hero.png"


def test_desktop_clone_input_physics_and_cleanup() -> None:
    """A real input-driven loop creates a clone, moves both bodies and retires the copy."""
    stage = Stage(physics=True)
    stage.gamepads[0].map_key(Key.A, GamepadButton.LEFT)
    stage.gamepads[0].map_key(Key.B, GamepadButton.B)
    stage.gamepads[0].map_key(Key.R, GamepadButton.SELECT)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    stage.gamepads[0].map_key(Key.Z, GamepadButton.R)
    stage.physics.gravity = (0, 0)
    hero = Sprite(IMAGE, x=-100)
    stage.add(hero)
    hero.body.velocity = (20, 0)
    copies: list[Sprite] = []
    births: list[Sprite] = []

    @hero.on_clone
    def born(event: Event[Sprite, None]) -> None:
        assert event.source is hero and event.data is None
        actor = event.target
        assert actor.body.velocity == (0, 0)
        assert actor.body_type is BodyType.DYNAMIC
        actor.body.velocity = (100, 0)
        births.append(actor)

    @stage.on_button_down(GamepadButton.A, gamepad=stage.gamepads[0])
    def spawn(event: Event[Stage, GamepadPress]) -> None:
        clone = hero.clone()
        clone.position = (100, 0)
        copies.append(clone)
        assert not births

    @stage.on_update
    def exercise(event: Event[Stage, float]) -> None:
        if stage.time == 0:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        if stage.time >= 0.2:
            assert len(copies) == len(births) == 1
            assert -100 < hero.x < -90 and copies[0].x > 110
            assert len(stage.physics._bodies) == 2
            stale = copies[0].body
            stage.remove(copies[0])
            assert stale._native is None and len(stage.physics._bodies) == 1
            assert len(stage._clone_handlers) == 1
            stage.stop()

    stage.run()
    assert not stage.objects and not stage._pending and not stage._clone_handlers
    assert not stage._actions and not stage._voices and not stage.physics._bodies
    assert hero._stage is None and copies[0]._stage is None
    assert pygame.display.get_surface() is None


@dataclass
class EnemyState:
    health: int = 10
    inventory: list[str] = field(default_factory=list[str])


@pytest.fixture
def world() -> Iterator[Stage]:
    """Each example owns a stage and retires registrations even when an assertion fails."""
    stage = Stage()
    stage.gamepads[0].map_key(Key.A, GamepadButton.LEFT)
    stage.gamepads[0].map_key(Key.B, GamepadButton.B)
    stage.gamepads[0].map_key(Key.R, GamepadButton.SELECT)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    stage.gamepads[0].map_key(Key.Z, GamepadButton.R)
    yield stage
    close(stage)


def ticks(stage: Stage, count: int) -> None:
    """Use the real event/action/physics order with a deterministic wall clock."""
    if stage._state == "new":
        stage._state = "running"
        stage._last_wall = 0
        for handler in tuple(stage._starts):
            _trigger(stage, handler)
        _step(stage)
    for _ in range(count):
        advance(stage, (stage._last_wall or 0) + 1 / stage.tick_rate)


def test_snapshot_assets_state_and_read_only_origin(world: Stage) -> None:
    """Cloning shares immutable pixels but preserves current fields in a distinct state root."""
    source = Sprite(IMAGE, state=EnemyState, x=12, y=-3, direction=270, scale=2, layer=8)
    source.visible = False
    source.rotation_style = RotationStyle.LEFT_RIGHT
    source.state.health = 7
    source.state.inventory.append("coin")
    world.add(source)
    clone = source.clone()
    assert not source.is_clone and clone.is_clone
    assert clone in world.objects and clone._stage is world
    assert clone.costume is source.costume
    assert clone.position == (12, -3) and clone.direction == 270 and clone.scale == 2
    assert clone.layer == 8 and not clone.visible
    assert clone.rotation_style is RotationStyle.LEFT_RIGHT
    assert clone.state is not source.state and type(clone.state) is EnemyState
    assert clone.state.health == 7 and clone.state.inventory is source.state.inventory
    clone.state.health -= 1
    assert source.state.health == 7
    clone.state.inventory = list(clone.state.inventory)
    clone.state.inventory.append("key")
    assert source.state.inventory == ["coin"]
    with pytest.raises(AttributeError):
        setattr(clone, "is_clone", False)  # noqa: B010 -- test the read-only runtime boundary


def test_clone_start_is_deferred_inherited_once_and_has_source(world: Stage) -> None:
    """Initialization sees the customized copy and never replays an ordinary start handler."""
    source = Sprite(IMAGE)
    world.add(source)
    events: list[tuple[object, Sprite, float]] = []
    starts: list[Sprite] = []

    @source.on_start
    def started(event: Event[Sprite, None]) -> None:
        starts.append(event.target)

    @source.on_clone
    def born(event: Event[Sprite, None]) -> None:
        assert event.data is None
        events.append((event.source, event.target, event.target.x))

    clone = source.clone()
    clone.x = 40
    assert events == []
    ticks(world, 1)
    assert starts == [source] and events == [(source, clone, 40)]
    ticks(world, 4)
    assert len(events) == 1
    world.remove(source)
    child = clone.clone()
    child.x = 80
    ticks(world, 1)
    assert events[-1] == (clone, child, 80)
    assert clone in world.objects and child in world.objects


def test_bound_scripts_and_returned_scripts_use_clone_receiver(world: Stage) -> None:
    """Both adapter forms bind future runs to Event.target instead of the original actor."""
    source = Sprite(IMAGE)
    world.add(source)
    source.on_button_down(GamepadButton.LEFT, Script(Sprite).move(5), gamepad=world.gamepads[0])

    @source.on_button_down(GamepadButton.B, gamepad=world.gamepads[0])
    def move(event: Event[Sprite, GamepadPress]) -> Script[Sprite]:
        return event.target.sequence().move(7)

    clone = source.clone()
    clone.x = 100
    ticks(world, 1)
    world._pending.extend(
        (
            GamepadPress(world.gamepads[0], GamepadButton.LEFT),
            GamepadPress(world.gamepads[0], GamepadButton.B),
        )
    )
    ticks(world, 1)
    assert source.x == 12 and clone.x == 112
    assert not world._actions


def test_clone_start_script_update_and_broadcast_inheritance(world: Stage) -> None:
    """Direct startup scripts, updates and targeted messages operate independently."""
    source = Sprite(IMAGE, state=EnemyState)
    world.add(source)
    source.on_clone(Script(Sprite).move(10))
    message = Message[int]("damage")
    updates: list[Sprite[EnemyState]] = []

    @source.on_update
    def updated(event: Event[Sprite[EnemyState], float]) -> None:
        updates.append(event.target)

    @source.on_broadcast(message)
    def damaged(event: Event[Sprite[EnemyState], int]) -> None:
        assert event.source is source
        event.target.state.health -= event.data

    clone = source.clone()
    clone.x = 100
    ticks(world, 1)
    assert source.x == 0 and clone.x == 110 and updates == [source, clone]
    source.broadcast(message, 3, to=clone)
    ticks(world, 2)
    assert source.state.health == 10 and clone.state.health == 7
    source.broadcast(message, 2)
    ticks(world, 2)
    assert source.state.health == 8 and clone.state.health == 5


def test_inherited_click_hits_only_the_topmost_receiver(world: Stage) -> None:
    """The copied callback remains actor-scoped and does not duplicate stage observers."""
    source = Sprite(IMAGE)
    world.add(source)
    clicked: list[Sprite] = []
    observed: list[object] = []

    @source.on_click
    def click(event: Event[Sprite, Click]) -> None:
        clicked.append(event.target)

    @world.on_click
    def observe(event: Event[Stage, Click]) -> None:
        observed.append(event.target)

    clone = source.clone()
    clone.x = 100
    ticks(world, 1)
    world._pending.append(((100, 0), MouseButton.LEFT))
    ticks(world, 1)
    assert clicked == [clone] and observed == [world]


def test_busy_and_keyboard_turbo_progress_are_not_inherited(world: Stage) -> None:
    """An already-busy original neither blocks the copy nor transfers its repeat deadline."""
    source = Sprite(IMAGE)
    world.add(source)
    source.on_button_down(
        GamepadButton.LEFT,
        Script(Sprite).glide_by(x=60, seconds=1),
        repeat=0.25,
        when_busy=WhenBusy.IGNORE,
        gamepad=world.gamepads[0],
    )
    ticks(world, 1)
    world._held_keys.add(Key.A)
    world._pending.append(GamepadPress(world.gamepads[0], GamepadButton.LEFT))
    ticks(world, 5)
    original = world._actions[0]
    clone = source.clone()
    clone.x = 100
    bindings = world._gamepad_handlers[(world.gamepads[0], GamepadButton.LEFT)]
    assert bindings[0].next_repeat is not None and bindings[1].next_repeat is None
    assert bindings[0].handler is not bindings[1].handler
    assert bindings[1].handler.when_busy is WhenBusy.IGNORE
    world._pending.append(GamepadPress(world.gamepads[0], GamepadButton.LEFT))
    ticks(world, 1)
    assert not original.cancelled and len(world._actions) == 2
    ticks(world, 5)
    assert source.x < 20 and clone.x > 100


def test_gamepad_bindings_keep_slot_grouping_but_get_new_busy_state(world: Stage) -> None:
    """All player slots share a registration within one actor, never across its copies."""
    source = Sprite(IMAGE)
    world.add(source)
    hits: list[tuple[Sprite, int]] = []

    @source.on_button_down(GamepadButton.A, repeat=0.1)
    def pressed(event: Event[Sprite, GamepadPress]) -> None:
        hits.append((event.target, event.data.gamepad.index))

    clone = source.clone()
    original_handlers = [items[0].handler for items in world._gamepad_handlers.values()]
    copied_handlers = [items[1].handler for items in world._gamepad_handlers.values()]
    assert len(set(original_handlers)) == len(set(copied_handlers)) == 1
    assert original_handlers[0] is not copied_handlers[0]
    ticks(world, 1)
    world._pending.append(GamepadPress(world.gamepads[1], GamepadButton.A))
    ticks(world, 1)
    assert hits == [(source, 1), (clone, 1)]


def test_later_registrations_affect_only_future_clones(world: Stage) -> None:
    """Copies snapshot bindings rather than retaining an implicit live link to their source."""
    source = Sprite(IMAGE)
    world.add(source)
    old = source.clone()
    source.on_button_down(GamepadButton.LEFT, Script(Sprite).move(4), gamepad=world.gamepads[0])
    new = source.clone()
    ticks(world, 1)
    world._pending.append(GamepadPress(world.gamepads[0], GamepadButton.LEFT))
    ticks(world, 1)
    assert source.x == new.x == 4 and old.x == 0


def test_removal_cancels_pending_start_and_readding_does_not_restore_handlers(world: Stage) -> None:
    """A removed clone leaves no queued callback, inherited registrations or resumed work."""
    source = Sprite(IMAGE)
    world.add(source)
    called: list[Sprite] = []

    @source.on_clone
    def born(event: Event[Sprite, None]) -> None:
        called.append(event.target)

    source.on_button_down(GamepadButton.LEFT, Script(Sprite).move(1), gamepad=world.gamepads[0])
    clone = source.clone()
    world.remove(clone)
    assert not world._pending and len(world._clone_handlers) == 1
    world.add(clone)
    ticks(world, 1)
    world._pending.append(GamepadPress(world.gamepads[0], GamepadButton.LEFT))
    ticks(world, 1)
    assert called == [] and clone.x == 0 and source.x == 1 and clone.is_clone


def test_pause_and_suspension_preserve_pending_clone_starts(world: Stage) -> None:
    """Clearing held input never discards initialization, which waits until simulation resumes."""
    source = Sprite(IMAGE)
    world.add(source)
    source.on_clone(Script(Sprite).move(20))
    ticks(world, 1)
    world.pause()
    clone = source.clone()
    _clear_input(world)
    ticks(world, 10)
    assert clone.x == 0 and len(world._pending) == 1
    world._set_pause("focus", True)
    world.resume()
    ticks(world, 2)
    assert clone.x == 0
    world._set_pause("focus", False)
    ticks(world, 2)
    assert clone.x == 20 and not world._pending


def test_source_action_cancellation_does_not_own_the_new_clone(world: Stage) -> None:
    """Queued clone starts are not structured children of the action that created them."""
    source = Sprite(IMAGE)
    world.add(source)
    source.on_clone(Script(Sprite).glide_by(x=60, seconds=1))
    message = Message[None]("spawn")
    copies: list[Sprite] = []

    @source.on_broadcast(message)
    def spawn(event: Event[Sprite, None]) -> None:
        copies.append(event.target.clone())

    ticks(world, 1)
    action = source.act(Script(Sprite).broadcast(message).wait(10))
    ticks(world, 2)
    assert copies
    action.cancel()
    world.remove(source)
    ticks(world, 10)
    assert copies[0].x > 0 and copies[0] in world.objects


def test_no_actions_or_bubbles_are_copied(world: Stage) -> None:
    """Only the sampled visual transfers; source animation and dialogue keep their own progress."""
    source = Sprite(IMAGE)
    world.add(source)
    first = source.costume
    second = first.flipped(horizontal=True)
    source.costumes((first, second), fps=4)
    source.say("Original", seconds=1)
    ticks(world, 17)
    assert source.costume is second and source._bubble is not None
    count = len(world._actions)
    clone = source.clone()
    assert clone.costume is second and clone._bubble is None
    assert len(world._actions) == count
    source.costume = first
    assert clone.costume is second


def test_puppet_parts_pose_and_state_have_the_declared_ownership(world: Stage) -> None:
    """A rig shares immutable definitions while its attachment mapping and state are independent."""
    rig = Skeleton({"root": Joint(None), "arm": Joint("root", offset=(10, 0))})
    source = Puppet(rig, parts={"root": IMAGE, "arm": IMAGE}, state=EnemyState)
    source.position, source.direction, source.scale = (30, -40), 120, 0.5
    source.layer, source.visible = 9, False
    source.rotation_style = RotationStyle.NONE
    world.add(source)
    rest = source.pose
    bent = rest.with_angles({"arm": 60})
    source.poses((rest, bent), fps=2)
    ticks(world, 15)
    clone = source.clone()
    assert clone.skeleton is rig and clone._parts is not source._parts
    assert clone.parts["arm"] is source.parts["arm"]
    assert dict(clone.pose.angles) == dict(source.pose.angles)
    assert clone.position == source.position and clone.direction == source.direction
    assert clone.scale == 0.5 and clone.layer == 9 and not clone.visible
    assert clone.rotation_style is RotationStyle.NONE
    assert clone.state is not source.state
    replacement = Costume(IMAGE).flipped(vertical=True)
    clone.set_part_costume("arm", replacement)
    ticks(world, 2)
    assert clone.parts["arm"] is replacement and source.parts["arm"] is not replacement
    frozen = dict(clone.pose.angles)
    ticks(world, 20)
    assert dict(clone.pose.angles) == frozen and source.pose is bent


def test_limits_detached_closed_and_subclass_sources(world: Stage) -> None:
    """Quota and unsupported sources fail before membership or registrations change."""
    source = Sprite(IMAGE)
    with pytest.raises(StageError, match="attached"):
        source.clone()
    world.add(source)
    clones = [source.clone() for _ in range(300)]
    with pytest.raises(StageError, match="300 clones"):
        source.clone()
    assert len(world.objects) == 301 and len(world._pending) == 300
    world.remove(clones.pop())
    replacement = source.clone()
    assert replacement.is_clone and len(world.objects) == 301
    world.clear()
    assert not world._pending

    class CustomSprite(Sprite):
        pass

    custom = CustomSprite(IMAGE)
    world.add(custom)
    with pytest.raises(TypeError, match="factory"):
        custom.clone()
    close(world)
    with pytest.raises(StageError):
        custom.clone()


def test_failed_state_copy_and_registration_commit_leave_no_partial_clone(world: Stage) -> None:
    """Failures before and after attachment preserve the source and roll back the new copy."""
    failure = LookupError("state copy failed")

    @dataclass
    class BadState:
        def __copy__(self) -> object:
            raise failure

    source = Sprite(IMAGE, state=BadState)
    world.add(source)
    with pytest.raises(LookupError) as caught:
        source.clone()
    assert caught.value is failure and list(world.objects) == [source] and not world._pending
    valid = Sprite(IMAGE)
    world.add(valid)
    valid.on_clone(Script(Sprite).wait(1))
    with (
        patch("plocks._cloning._inherit", side_effect=RuntimeError("inherit failed")),
        pytest.raises(RuntimeError, match="inherit failed"),
    ):
        valid.clone()
    assert list(world.objects) == [source, valid] and len(world._clone_handlers) == 1
    assert not world._pending


def test_repeated_spawning_does_not_accumulate_registrations(world: Stage) -> None:
    """All copied and clone-local registry entries are released on each removal."""
    source = Sprite(IMAGE)
    world.add(source)
    message = Message[None]("hello")
    source.on_clone(Script(Sprite).wait(10))
    source.on_button_down(
        GamepadButton.LEFT, Script(Sprite).wait(10), repeat=0.1, gamepad=world.gamepads[0]
    )
    source.on_button_down(GamepadButton.A, Script(Sprite).wait(10))
    source.on_click(Script(Sprite).wait(10))
    source.on_broadcast(message, Script(Sprite).wait(10))

    @source.on_update
    def update(event: Event[Sprite, float]) -> None:
        pass

    ticks(world, 1)
    for _ in range(200):
        clone = source.clone()
        clone.on_button_down(GamepadButton.R, Script(Sprite).wait(10), gamepad=world.gamepads[0])
        clone.on_broadcast(Message[None]("temporary"), Script(Sprite).wait(10))
        ticks(world, 1)
        world.remove(clone)
        assert list(world.objects) == [source] and not world._actions and not world._pending
        assert len(world._gamepad_handlers) == 5
        assert len(world._message_handlers) == len(world._clicks) == 1
        assert (
            len(world._gamepad_handlers[(world.gamepads[0], GamepadButton.LEFT)])
            == len(world._updates)
            == len(world._clone_handlers)
            == 1
        )
        assert all(len(bindings) == 1 for bindings in world._gamepad_handlers.values())


def test_clone_callback_failure_preserves_traceback_and_closes_everything() -> None:
    """The desktop driver observes initialization errors and retires clones and registrations."""
    stage = Stage(physics=True)
    stage.gamepads[0].map_key(Key.A, GamepadButton.LEFT)
    stage.gamepads[0].map_key(Key.B, GamepadButton.B)
    stage.gamepads[0].map_key(Key.R, GamepadButton.SELECT)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    stage.gamepads[0].map_key(Key.Z, GamepadButton.R)
    source = Sprite(IMAGE)
    stage.add(source)
    error = LookupError("clone initialization")

    @source.on_clone
    def fail(event: Event[Sprite, None]) -> None:
        raise error

    source.clone()
    with pytest.raises(LookupError) as caught:
        stage.run()
    assert caught.value is error
    assert not stage.objects and not stage.physics._bodies and not stage._clone_handlers
    assert not stage._pending and pygame.display.get_surface() is None


def test_state_copy_preserves_slotted_frozen_and_non_init_fields(world: Stage) -> None:
    """Standard Python copy semantics preserve values without rerunning dataclass initialization."""
    calls: list[object] = []

    @dataclass(frozen=True, slots=True)
    class FrozenState:
        health: int = 10
        derived: int = field(init=False, default=20)

        def __post_init__(self) -> None:
            calls.append(self)
            object.__setattr__(self, "derived", 30)

    source = Sprite(IMAGE, state=FrozenState)
    world.add(source)
    clone = source.clone()
    assert len(calls) == 1 and clone.state is not source.state
    assert clone.state.health == 10 and clone.state.derived == 30


@pytest.mark.parametrize("result", ["self", "none", "wrong type"])
def test_invalid_state_copy_results_do_not_break_the_declared_type(
    world: Stage, result: str
) -> None:
    """A custom copy hook cannot replace a typed dataclass root with None or a different type."""

    @dataclass
    class CustomState:
        health: int = 10

        def __copy__(self) -> object:
            if result == "self":
                return self
            return None if result == "none" else object()

    source = Sprite(IMAGE, state=CustomState)
    world.add(source)
    with pytest.raises(TypeError, match="distinct instance of the same type"):
        source.clone()
    assert list(world.objects) == [source] and not world._pending


def test_partial_inheritance_rollback_and_source_repeat_are_preserved(world: Stage) -> None:
    """Rolling back after registry mutation drops only the copy's bindings and deadlines."""
    from plocks._cloning import _inherit

    source = Sprite(IMAGE)
    world.add(source)
    source.on_clone(Script(Sprite).wait(1))
    source.on_button_down(
        GamepadButton.LEFT, Script(Sprite).wait(1), repeat=0.2, gamepad=world.gamepads[0]
    )
    binding = world._gamepad_handlers[(world.gamepads[0], GamepadButton.LEFT)][0]
    binding.next_repeat = 12

    def fail(stage: Stage, before: Sprite | Puppet, after: Sprite | Puppet) -> None:
        _inherit(stage, before, after)
        raise LookupError("after inheritance")

    with (
        patch("plocks._cloning._inherit", side_effect=fail),
        pytest.raises(LookupError, match="after inheritance"),
    ):
        source.clone()
    assert list(world.objects) == [source] and not world._pending
    assert (
        len(world._clone_handlers)
        == len(world._gamepad_handlers[(world.gamepads[0], GamepadButton.LEFT)])
        == 1
    )
    assert (
        world._gamepad_handlers[(world.gamepads[0], GamepadButton.LEFT)][0] is binding
        and binding.next_repeat == 12
    )


def test_generations_are_queued_without_recursive_delivery(world: Stage) -> None:
    """A clone created by its parent's start waits for the next event-dispatch snapshot."""
    source = Sprite(IMAGE, state=EnemyState)
    source.state.health = 3
    world.add(source)
    births: list[Sprite[EnemyState]] = []

    @source.on_clone
    def reproduce(event: Event[Sprite[EnemyState], None]) -> None:
        clone = event.target
        births.append(clone)
        if clone.state.health > 0:
            clone.state.health -= 1
            clone.clone()

    source.clone()
    for count in range(1, 5):
        ticks(world, 1)
        assert len(births) == count
    ticks(world, 2)
    assert len(births) == 4 and not world._pending


def test_clone_can_remove_itself_during_its_start(world: Stage) -> None:
    """Self-removal skips subsequent snapshot handlers and leaves no queued work."""
    source = Sprite(IMAGE)
    world.add(source)
    reached: list[Sprite] = []

    @source.on_clone
    def remove(event: Event[Sprite, None]) -> None:
        world.remove(event.target)

    @source.on_clone
    def later(event: Event[Sprite, None]) -> None:
        reached.append(event.target)

    clone = source.clone()
    ticks(world, 1)
    assert clone._stage is None and not reached and not world._pending
    assert len(world._clone_handlers) == 2


def test_cloning_inside_update_uses_a_registration_snapshot(world: Stage) -> None:
    """New update registrations do not alter the callback list already being dispatched."""
    source = Sprite(IMAGE)
    world.add(source)
    seen: list[Sprite] = []
    copies: list[Sprite] = []

    @source.on_update
    def update(event: Event[Sprite, float]) -> None:
        seen.append(event.target)
        if not copies:
            copies.append(event.target.clone())

    ticks(world, 1)
    assert seen == [source]
    ticks(world, 1)
    assert seen == [source, source, copies[0]]


@pytest.mark.parametrize("kind", ["sprite", "puppet"])
def test_rendered_clone_matches_transformed_source(world: Stage, kind: str) -> None:
    """Copied anchors, rotations, scaling and Puppet parts render the same relative pixels."""
    from math import ceil, floor

    from plocks import Actor
    from plocks._render import frame

    costume = Costume(IMAGE, anchor=(0, 0))
    source: Actor
    if kind == "sprite":
        source = Sprite(costume)
    else:
        source = Puppet(Skeleton({"root": Joint(None)}), parts={"root": costume})
    source.position, source.direction, source.scale = (-70, 30), 37, 1.5
    source.rotation_style = RotationStyle.LEFT_RIGHT
    world.camera = (17, -12)
    world.add(source)
    clone = source.clone()
    clone.position = (70, -30)
    ticks(world, 1)
    target = pygame.display.set_mode((world.width, world.height))
    world._target = target
    frame(world)

    def region(actor: Actor) -> bytes:
        left, top = world.to_screen((actor.bounds.left, actor.bounds.top))
        box = pygame.Rect(
            floor(left) - 1,
            floor(top) - 1,
            ceil(actor.bounds.width) + 3,
            ceil(actor.bounds.height) + 3,
        )
        return pygame.image.tobytes(target.subsurface(box), "RGBA")

    assert region(source) == region(clone)


def test_clone_start_overflow_is_observed_and_all_bodies_are_retired() -> None:
    """The existing action limit bounds clone scripts and its error triggers full driver cleanup."""
    stage = Stage(physics=True)
    stage.gamepads[0].map_key(Key.A, GamepadButton.LEFT)
    stage.gamepads[0].map_key(Key.B, GamepadButton.B)
    stage.gamepads[0].map_key(Key.R, GamepadButton.SELECT)
    stage.gamepads[0].map_key(Key.SPACE, GamepadButton.A)
    stage.gamepads[0].map_key(Key.Z, GamepadButton.R)
    source = Sprite(IMAGE)
    stage.add(source)
    source.on_clone(Script(Sprite).wait(10))
    clones = [source.clone() for _ in range(129)]
    with pytest.raises(StageError, match="128-execution"):
        stage.run()
    assert not stage.objects and not stage._actions and not stage._clone_handlers
    assert not stage.physics._bodies and not stage._pending
    assert all(clone._stage is None for clone in clones)


def test_readding_a_clone_cannot_bypass_the_membership_quota(world: Stage) -> None:
    """The membership mutation boundary enforces the limit for detached copies as well."""
    source = Sprite(IMAGE)
    world.add(source)
    spare = source.clone()
    world.remove(spare)
    for _ in range(300):
        source.clone()
    with pytest.raises(StageError, match="300 clones"):
        world.add(spare)
    assert spare._stage is None and len(world.objects) == 301


def test_queued_clone_start_survives_source_removal(world: Stage) -> None:
    """The event borrows its sender until delivery; it does not require the source to remain attached."""
    source = Sprite(IMAGE)
    world.add(source)
    origins: list[object] = []

    @source.on_clone
    def begin(event: Event[Sprite, None]) -> Script[Sprite]:
        origins.append(event.source)
        return event.target.sequence().move(20)

    clone = source.clone()
    world.remove(source)
    ticks(world, 1)
    assert origins == [source] and clone.x == 20 and clone in world.objects


def test_resuming_during_paused_input_keeps_clone_start_order(world: Stage) -> None:
    """A resume key cannot start later clones ahead of earlier paused initialization events."""
    source = Sprite(IMAGE)
    world.add(source)
    births: list[Sprite] = []

    @source.on_clone
    def born(event: Event[Sprite, None]) -> None:
        births.append(event.target)

    @world.on_button_down(GamepadButton.SELECT, gamepad=world.gamepads[0])
    def resume(event: Event[Stage, GamepadPress]) -> None:
        world.resume()

    ticks(world, 1)
    world.pause()
    first, second = source.clone(), source.clone()
    world._pending.insert(1, GamepadPress(world.gamepads[0], GamepadButton.SELECT))
    ticks(world, 1)
    assert not world.paused and not births
    ticks(world, 2)
    assert births == [first, second]


def test_message_resume_does_not_initialize_clones_in_a_paused_ui_cycle(world: Stage) -> None:
    """The engine phase remains explicit even when a message removes the pause reason."""
    source = Sprite(IMAGE)
    world.add(source)
    signal = Message[None]("resume")
    births: list[Sprite] = []

    @source.on_clone
    def born(event: Event[Sprite, None]) -> None:
        births.append(event.target)

    @world.on_broadcast(signal)
    def resume(event: Event[Stage, None]) -> None:
        world.resume()

    ticks(world, 1)
    world.broadcast(signal)
    ticks(world, 1)
    assert world._messages
    world.pause()
    clone = source.clone()
    ticks(world, 1)
    assert not world.paused and not births
    ticks(world, 2)
    assert births == [clone]


def test_deferring_one_clone_keeps_later_starts_in_order(world: Stage) -> None:
    """A pause followed by a resume in one input snapshot cannot let a later clone overtake."""
    source = Sprite(IMAGE)
    world.add(source)
    births: list[Sprite] = []

    @source.on_clone
    def born(event: Event[Sprite, None]) -> None:
        births.append(event.target)
        if len(births) == 1:
            world.pause()

    @world.on_button_down(GamepadButton.SELECT, gamepad=world.gamepads[0])
    def resume(event: Event[Stage, GamepadPress]) -> None:
        world.resume()

    ticks(world, 1)
    first, second, third = source.clone(), source.clone(), source.clone()
    world._pending.insert(2, GamepadPress(world.gamepads[0], GamepadButton.SELECT))
    ticks(world, 1)
    assert births == [first]
    ticks(world, 2)
    assert births == [first, second, third]
