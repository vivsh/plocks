"""Positive typing and editor hover inspection surface for the synchronous API."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import assert_type

from plocks import (
    Action,
    Actor,
    BodyType,
    Box,
    Click,
    Ease,
    Event,
    Key,
    KeyDown,
    Message,
    Not,
    Puppet,
    Script,
    Sprite,
    Stage,
    TileMap,
)


def main() -> None:
    stage = Stage(physics=True)
    hero = Sprite(Path("hero.png"), body_type=BodyType.NONE)
    person = Puppet.stick_figure()
    stage.add(hero)
    stage.add(person)
    patrol = Script(Sprite).repeat(10).glide_by(x=10, seconds=0.2).costumes((hero.costume,), fps=5)
    hero.on_start(patrol)
    hero.sequence().set_costume(hero.costume)
    person.repeat(2).poses((person.pose,), fps=2)
    common = Script().when(Not(KeyDown(Key.LEFT)), then=Script().wait(0.1))
    hero.act(common)
    person.act(common)
    hero.costume = (
        hero.costume.flipped(horizontal=True)
        .cropped(x=0, y=0, width=8, height=8)
        .with_anchor(x=4, y=8)
        .rotated(90)
        .resized(width=16, height=16)
    )

    @hero.on_key_down(Key.SPACE)
    def jump(event: Event[Sprite, Key]) -> Action:
        actor = event.target
        up = actor.glide_by(y=100, seconds=0.3, easing=Ease.OUT)
        return actor.glide_by(y=-100, seconds=0.3, easing=Ease.IN, after=up)

    key_command = Message[Key]("key command")
    hero.on_broadcast(key_command)(jump)
    hero.broadcast(key_command, Key.SPACE, to=hero)

    steps = Message[int]("steps")

    @hero.on_broadcast(steps)
    def walk(event: Event[Sprite, int]) -> Script[Sprite]:
        return Script(Sprite).glide_by(x=event.data, seconds=1)

    @person.on_click
    def answer(event: Event[Puppet, Click]) -> Action:
        actor = event.target
        position, button = event.data
        return actor.say(f"Clicked {button.name} at {position}", seconds=1)

    @hero.on_update
    def move(event: Event[Sprite, float]) -> None:
        actor = event.target
        dt = event.data
        actor.x += 20 * dt

    ready = Message[None]("ready")

    @person.on_broadcast(ready)
    def wave(event: Event[Puppet, None]) -> Script[Puppet]:
        return event.target.sequence().set_pose(event.target.pose)

    @stage.on_broadcast(steps)
    def adjust_volume(event: Event[Stage, int]) -> None:
        event.target.volume = min(1.0, event.data / 100)

    person.body.shape = Box(20, 80)
    person.body.rotation_locked = True
    target: Actor = hero if stage.keyboard.is_down(Key.H) else person
    target.wait(0.2)


@dataclass
class PlayerState:
    """Ordinary dataclass fields retain their types through the actor and its events."""

    health: int = 100
    speed: float = 1
    alive: bool = True
    coins: list[int] = field(default_factory=list[int])


@dataclass
class GameState:
    """Shared values belong directly to this Stage's own dataclass instance."""

    score: int = 0


def state_example() -> None:
    """State types follow Sprite, Puppet, Stage and their event receivers."""
    from plocks import Joint, Skeleton

    stage = Stage(state=GameState)
    hero = Sprite(Path("hero.png"), state=PlayerState)
    person = Puppet(
        Skeleton({"root": Joint(parent=None)}),
        parts={"root": Path("hero.png")},
        state=PlayerState,
    )
    assert_type(stage, Stage[GameState])
    assert_type(hero, Sprite[PlayerState])
    assert_type(person, Puppet[PlayerState])
    assert_type(Stage().state, None)
    assert_type(Stage(state=None).state, None)
    assert_type(Sprite(Path("hero.png")).state, None)
    assert_type(Sprite(Path("hero.png"), state=None).state, None)
    assert_type(Puppet(person.skeleton, parts=person.parts).state, None)
    assert_type(Puppet.stick_figure().state, None)

    def accept_broad(sprite: Sprite, shared_stage: Stage, puppet: Puppet) -> None:
        assert_type(sprite.state, object)
        assert_type(shared_stage.state, object)
        assert_type(puppet.state, object)

    accept_broad(hero, stage, person)
    stage.add(hero)
    stage.add(person)
    hero.state.health -= 1
    hero.state.speed = 0.5
    hero.state.coins.append(1)
    stage.state.score += 1
    health_changed = Message[int]("health changed")

    @hero.on_start
    def started(event: Event[Sprite[PlayerState], None]) -> Script[Sprite]:
        event.target.state.health = 100
        event.target.state.alive = True
        return hero.sequence().say("Ready!", seconds=1)

    @hero.on_click
    def clicked(event: Event[Sprite[PlayerState], Click]) -> None:
        event.target.state.health += 1

    @hero.on_broadcast(health_changed)
    def health(event: Event[Sprite[PlayerState], int]) -> None:
        event.target.state.health += event.data
        if event.target.state.health <= 0:
            event.target.state.alive = False

    hero.on_key_down(Key.H, Script().wait(0.1).broadcast(health_changed, -10, to=hero))

    @person.on_key_down(Key.H)
    def puppet_key(event: Event[Puppet[PlayerState], Key]) -> None:
        event.target.state.health -= 1

    @person.on_start
    def puppet_start(event: Event[Puppet[PlayerState], None]) -> Script[Puppet]:
        event.target.state.alive = True
        event.target.state.health = 100
        return person.sequence().wait(0.1)

    @stage.on_start
    def stage_start(event: Event[Stage[GameState], None]) -> None:
        event.target.state.score = 0

    @stage.on_click
    def stage_click(event: Event[Stage[GameState], Click]) -> None:
        event.target.state.score += 1

    @stage.on_update
    def stage_update(event: Event[Stage[GameState], float]) -> None:
        event.target.state.score += 1


def imported_controls() -> None:
    """Exports and typed input preserve dataclass-specific receiver information."""
    from plocks import (
        GamepadButton,
        GamepadDown,
        GamepadLayout,
        GamepadPress,
        PixeloramaSheet,
        TiledMap,
    )

    stage = Stage(state=GameState, gamepad_count=2, gamepad_layout=GamepadLayout.XBOX)
    art = PixeloramaSheet(Path("hero.png"))
    level = TiledMap(Path("level.tmj"))
    hero = Sprite(art.frames[0], state=PlayerState)
    person = Puppet.stick_figure()
    stage.add(hero)
    stage.add(person)
    for layer in level.layers.values():
        stage.add(layer)
    hero.position = level.points["Spawns/start"]
    player = stage.gamepads[0]
    player.map_key(Key.SPACE, GamepadButton.A)
    player.map_right_stick(left=Key.A, right=Key.D)
    hero.costumes(art.frames, durations=art.durations)
    hero.sequence().costumes(art.frames, fps=10)
    hero.on_key_down(Key.F, hero.sequence().move(1), repeat=0.1)
    hero.on_gamepad_button_down(GamepadButton.A, art.animation(), gamepad=player)

    @hero.on_gamepad_button_down(GamepadButton.B, gamepad=player, repeat=0.2)
    def shoot(event: Event[Sprite[PlayerState], GamepadPress]) -> Script[Sprite]:
        assert_type(event.data, GamepadPress)
        assert_type(event.target.state, PlayerState)
        event.target.state.health -= 1
        return event.target.sequence().say(event.data.button.name, seconds=0.1)

    @stage.on_gamepad_button_down(GamepadButton.START)
    def start(event: Event[Stage[GameState], GamepadPress]) -> None:
        event.target.state.score += event.data.gamepad.index

    @person.on_gamepad_button_down(GamepadButton.A)
    def pose(event: Event[Puppet, GamepadPress]) -> Script[Puppet]:
        return event.target.sequence().set_pose(event.target.pose)

    person.on_gamepad_button_down(GamepadButton.B, person.sequence().wait(1))
    stage.on_gamepad_button_down(GamepadButton.X, hero, hero.sequence().wait(1), gamepad=player)
    hero.sequence().when(GamepadDown(GamepadButton.A, player), then=hero.sequence().move(1))


def one_way_platforms() -> None:
    """Platform configuration remains fully typed through generic actors."""
    lift = Sprite("platform.png", body_type=BodyType.KINEMATIC, one_way=True)
    assert_type(lift.one_way, bool)
    terrain = TileMap(["P"], {"P": "platform.png"}, tile_size=(32, 16), one_way={"P"})
    assert_type(terrain.one_way, frozenset[str])
