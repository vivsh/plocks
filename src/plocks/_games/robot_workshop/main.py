"""Robot Workshop: build a moving arm, a wheeled cart, and a hanging chain."""

from dataclasses import dataclass

from plocks import (
    BodyType,
    Button,
    Canvas,
    Circle,
    Event,
    GamepadButton,
    GamepadPress,
    Hinge,
    Image,
    Key,
    Label,
    Motor,
    Sprite,
    Stage,
)


@dataclass
class Arm:
    base: Sprite
    upper: Sprite
    lower: Sprite
    shoulder: Hinge
    elbow: Hinge
    drive: Motor


@dataclass
class Cart:
    chassis: Sprite
    left: Sprite
    right: Sprite
    left_motor: Motor
    right_motor: Motor


# A fixed camera shows the workshop; buttons and labels stay on the screen.
stage = Stage(width=960, height=600, physics=True, background="#172536")
player = stage.gamepads[0]
stage.physics.gravity = (0, -600)
player.map_key(Key.R, GamepadButton.SELECT)
player.map_key(Key.LEFT, GamepadButton.LEFT)
player.map_key(Key.RIGHT, GamepadButton.RIGHT)
player.map_key(Key.X, GamepadButton.B)
beam = Image.rectangle(96, 14, color="steelblue", outline="lightblue")
wheel_picture = Image.circle(16, color="gold", outline="orange", outline_width=2)
floor = Sprite(beam.resized(940, 20), y=-230, body_type=BodyType.STATIC)
stage.add(floor)


# A factory is an ordinary function that builds and returns a named set of parts.
def build_arm(x: float) -> Arm:
    base = Sprite(beam.resized(80, 12), x=x, y=100, body_type=BodyType.STATIC)
    upper = Sprite(beam.resized(14, 60), x=x, y=70, layer=1)
    lower = Sprite(beam.resized(12, 60), x=x, y=10, layer=2)
    added: list[Sprite] = []
    try:
        for part in (base, upper, lower):
            stage.add(part)
            added.append(part)
        # Local anchors are measured from the middle of each picture.
        shoulder = stage.physics.hinge(
            base, upper, anchor_a=(0, 0), anchor_b=(0, 30), limits=(-100, 100)
        )
        elbow = stage.physics.hinge(
            upper, lower, anchor_a=(0, -30), anchor_b=(0, 30), limits=(-110, 110)
        )
        drive = shoulder.motor(speed=0, max_torque=90000)
        return Arm(base, upper, lower, shoulder, elbow, drive)
    except BaseException:
        # Removing created parts also disconnects their links if construction fails.
        for created in reversed(added):
            stage.remove(created)
        raise


def build_cart(x: float) -> Cart:
    chassis = Sprite(beam.resized(100, 18), x=x, y=-165)
    left = Sprite(wheel_picture, x=x - 32, y=-197)
    right = Sprite(wheel_picture, x=x + 32, y=-197)
    added: list[Sprite] = []
    try:
        for part in (chassis, left, right):
            stage.add(part)
            added.append(part)
        left.body.shape = Circle(16)
        right.body.shape = Circle(16)
        left.body.friction = right.body.friction = 1
        a = stage.physics.hinge(chassis, left, anchor_a=(-32, -32))
        b = stage.physics.hinge(chassis, right, anchor_a=(32, -32))
        return Cart(
            chassis,
            left,
            right,
            a.motor(speed=0, max_torque=15000),
            b.motor(speed=0, max_torque=15000),
        )
    except BaseException:
        for created in reversed(added):
            stage.remove(created)
        raise


arm = build_arm(-300)
cart = build_cart(200)
# Join each beam end to the next beam's start; every beam has its own body.
links: list[Sprite] = []
chain: list[Hinge] = []
for index in range(7):
    piece = Sprite(beam.resized(30, 10), x=-45 + index * 30, y=70)
    stage.add(piece)
    if links:
        joint = stage.physics.hinge(links[-1], piece, anchor_a=(15, 0), anchor_b=(-15, 0))
    else:
        joint = stage.physics.hinge((-60, 70), piece, anchor_b=(-15, 0))
    links.append(piece)
    chain.append(joint)

# A spring has its own resting length. Damping helps the bouncing settle down.
spring_ball = Sprite(wheel_picture, x=340, y=40)
stage.add(spring_ball)
spring_ball.body.shape = Circle(16)
spring = stage.physics.spring((340, 140), spring_ball, rest_length=70, stiffness=60, damping=8)

hint = Label("Arrows: drive. Hold Space/X: move the arm. R: new cart.", position=(0, 260), size=24)
cut = Button("Drop chain", position=(250, 180))
stage.add(hint)
stage.add(cut)


@stage.on_update
def controls(event: Event[Stage, float]) -> None:
    speed = 0
    if player.is_down(GamepadButton.RIGHT):
        speed += 240
    if player.is_down(GamepadButton.LEFT):
        speed -= 240
    cart.left_motor.speed = cart.right_motor.speed = speed
    arm_speed = 0
    if player.is_down(GamepadButton.A):
        arm_speed += 45
    if player.is_down(GamepadButton.B):
        arm_speed -= 45
    arm.drive.speed = arm_speed


@cut.on_click
def drop_chain(event: Event[Button, None]) -> None:
    chain[0].disconnect()
    event.target.enabled = False


@stage.on_button_down(GamepadButton.SELECT, gamepad=player)
def new_cart(event: Event[Stage, GamepadPress]) -> None:
    global cart
    # Make another assembly with the same factory; no hidden whole-group clone.
    for part in (cart.chassis, cart.left, cart.right):
        stage.remove(part)
    cart = build_cart(200)


@stage.on_draw
def draw(canvas: Canvas) -> None:
    canvas.connection(spring, color="#ffe09a", width=2)
    canvas.circle((340, 140), 5, color="#ffe09a")
    canvas.text("ROBOT ARM", (-410, 180), size=22, color="#ffe09a")
    canvas.text("HINGED CHAIN", (-60, 150), size=22, color="#ffe09a")
    canvas.text("MOTOR CART", (120, -90), size=22, color="#ffe09a")


if __name__ == "__main__":
    stage.run()
