"""Complete gameplay paths through the shared desktop driver."""

from pathlib import Path

import pytest

from plocks import Event, Sprite, Stage

IMAGE = Path(__file__).parent / "fixtures/games/state_proof/assets/hero.png"


def test_touch_collection_keeps_another_actor_moving_and_cleans_up() -> None:
    """The first touch path removes a pickup once without interrupting other updates."""
    stage = Stage()
    hero = Sprite(IMAGE)
    coin = Sprite(IMAGE)
    friend = Sprite(IMAGE, x=100)
    for actor in (hero, coin, friend):
        stage.add(actor)
    collected: list[Sprite] = []

    @hero.on_touch(coin)
    def collect(event: Event[Sprite, Sprite]) -> None:
        assert event.source is stage and event.target is hero
        collected.append(event.data)
        stage.remove(event.data)

    @friend.on_update
    def move(event: Event[Sprite, float]) -> None:
        event.target.x += 60 * event.data
        if stage.time >= 0.05:
            assert collected == [coin] and friend.x > 100
            stage.stop()

    stage.run()
    assert collected == [coin] and not stage.objects and not stage._touches
    assert friend._stage is hero._stage is coin._stage is None


def test_following_camera_tracks_movement_before_each_overlay() -> None:
    """The complete camera path preserves world/screen conversion during real frames."""
    from plocks import Bounds, Canvas

    stage = Stage(width=200, height=100)
    hero = Sprite(IMAGE, x=100)
    stage.add(hero)
    stage.follow(hero, bounds=Bounds(-500, -300, 500, 300))

    @hero.on_update
    def move(event: Event[Sprite, float]) -> None:
        event.target.x += 100 * event.data

    @stage.on_draw
    def observe(canvas: Canvas) -> None:
        assert stage.camera == hero.position
        assert stage.from_screen(stage.to_screen(hero.position)) == pytest.approx(hero.position)
        if stage.time >= 0.05:
            stage.stop()

    stage.run()
    assert stage._camera_follow is None


def test_maze_route_moves_while_another_actor_updates() -> None:
    """The first navigation path completes a wall detour in the real desktop loop."""
    from plocks import TileMap

    stage = Stage()
    world = TileMap([".....", ".###.", "....."], {"#": IMAGE}, tile_size=(32, 32), solid={"#"})
    hero, friend = Sprite(IMAGE), Sprite(IMAGE, x=150)
    hero.scale = 0.1
    hero.position = world.cell_center(row=1, column=0)
    for obj in (world, hero, friend):
        stage.add(obj)
    goal = world.cell_center(row=1, column=4)
    route = world.find_path(start=hero.position, goal=goal, actor=hero)
    assert route is not None
    trip = hero.follow_path(route, speed=1000)

    @friend.on_update
    def move(event: Event[Sprite, float]) -> None:
        event.target.x += event.data * 60
        assert stage.time < 2, "The bounded route must finish"
        if trip.done:
            assert hero.position == goal and friend.x > 150
            stage.stop()

    stage.run()
    assert trip.done and not trip.cancelled and not stage._actions


@pytest.mark.parametrize("input_kind", ["mouse", "keyboard", "logical"])
def test_ui_resumes_paused_game_and_updates_score_without_drawing_callbacks(
    input_kind: str,
) -> None:
    """Mouse/mapped keyboard/logical controls activate the same paused menu button."""
    import pygame

    from plocks import Button, GamepadButton, GamepadPress, Label, ProgressBar

    stage = Stage()
    hero = Sprite(IMAGE)
    score, health, resume = Label("Coins: 0"), ProgressBar(value=100), Button("Continue")
    for obj in (hero, score, health, resume):
        stage.add(obj)
    clicked: list[Button] = []

    @resume.on_click
    def play(event: Event[Button, None]) -> None:
        assert event.source is stage and stage.paused
        clicked.append(event.target)
        event.target.visible = False
        score.text = "Coins: 1"
        health.value = 75
        stage.resume()

    @stage.on_start
    def menu(event: Event[Stage, None]) -> None:
        stage.pause()
        stage.focus(resume)
        if input_kind == "mouse":
            pygame.event.post(
                pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN, button=1, pos=stage.to_screen((0, 0), world=False)
                )
            )
        elif input_kind == "keyboard":
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        else:
            stage._pending.append(GamepadPress(stage.gamepads[1], GamepadButton.A))

    @hero.on_update
    def move(event: Event[Sprite, float]) -> None:
        hero.x += event.data * 60
        if stage.time >= 0.05:
            assert clicked == [resume] and score.text == "Coins: 1" and health.value == 75
            stage.stop()

    stage.run()
    assert hero.x > 0 and stage.focused_button is None
    assert score._stage is health._stage is resume._stage is None


def test_world_rope_swings_disconnects_and_retires_before_bodies() -> None:
    """The first physical connection works in the real driver without stopping unrelated actors."""
    from plocks import BodyType, Canvas, Circle

    stage = Stage(physics=True)
    ball = Sprite(IMAGE, x=60, y=20)
    friend = Sprite(IMAGE, x=150, body_type=BodyType.NONE)
    stage.add(ball)
    stage.add(friend)
    ball.body.shape = Circle(10)
    rope = stage.physics.rope((0, 100), ball, length=100)
    release: list[float] = []

    @stage.on_draw
    def show(canvas: Canvas) -> None:
        canvas.connection(rope)

    @friend.on_update
    def move(event: Event[Sprite, float]) -> None:
        friend.x += event.data * 60
        if stage.time >= 0.15 and rope.connected:
            assert ball.x < 60
            release.append(ball.y)
            rope.disconnect()
            rope.disconnect()
        if stage.time >= 0.3:
            assert release and ball.y < release[0] and friend.x > 150
            stage.stop()

    stage.run()
    assert not rope.connected and not rope._native
    assert not stage.physics._connections and not stage.physics._bodies


def test_two_link_arm_uses_local_pivots_limits_and_a_torque_limited_motor() -> None:
    """A physical assembly moves under one solver and retires motors before its parts."""
    from math import degrees

    from plocks import BodyType, Box

    stage = Stage(physics=True)
    stage.physics.gravity = (0, 0)
    upper, lower = Sprite(IMAGE, y=60), Sprite(IMAGE, y=20)
    friend = Sprite(IMAGE, x=150, body_type=BodyType.NONE)
    for obj in (upper, lower, friend):
        stage.add(obj)
    upper.body.shape = Box(10, 40)
    lower.body.shape = Box(10, 40)
    shoulder = stage.physics.hinge((0, 80), upper, anchor_b=(0, 20))
    elbow = stage.physics.hinge(upper, lower, anchor_a=(0, -20), anchor_b=(0, 20), limits=(-30, 30))
    motor = elbow.motor(speed=90, max_torque=10000)

    @friend.on_update
    def move(event: Event[Sprite, float]) -> None:
        friend.x += event.data * 60
        if stage.time >= 0.6:
            pivot = elbow._native[0]
            relative = -degrees(pivot.b.angle - pivot.a.angle)
            assert 20 < relative < 32 and friend.x > 150
            stage.remove(upper)
            assert not shoulder.connected and not elbow.connected and not motor.connected
            assert lower in stage.objects
            stage.stop()

    stage.run()
    assert not stage.physics._connections and not stage.physics._bodies
