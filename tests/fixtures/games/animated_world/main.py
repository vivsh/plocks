from math import sin

from PIL import Image, ImageDraw

from plocks import (
    Canvas,
    Click,
    Costume,
    Ease,
    Event,
    HumanJoint,
    Key,
    KeyDown,
    Message,
    MouseButton,
    Not,
    Puppet,
    Script,
    Sound,
    Sprite,
    SpriteSheet,
    Stage,
    TiledBackground,
    TileMap,
)


def main() -> None:
    """Walk, edit the world, and meet a waving person. Works on desktop and the web."""
    stage = Stage(width=640, height=400, background="#122338")
    sky = Image.new("RGBA", (96, 96), "#122338")
    sky_pen = ImageDraw.Draw(sky)
    for x, y in ((12, 24), (62, 70), (85, 14)):
        sky_pen.ellipse((x, y, x + 2, y + 2), fill="#587294")
    background = TiledBackground(sky)
    stage.add(background)
    ground_image = Image.new("RGBA", (32, 32), "#304652")
    ground_pen = ImageDraw.Draw(ground_image)
    ground_pen.rectangle((0, 0, 31, 5), fill="#78cba4")
    ground_pen.line((0, 31, 31, 31), fill="#263d49")
    ground = Costume(ground_image)
    world = TileMap(
        ["." * 40, "." * 40, "#" * 40, "#" * 40],
        {"#": ground},
        tile_size=(32, 32),
        solid={"#"},
        x=-320,
        y=-36,
        layer=-10,
    )
    stage.add(world)
    sheet = SpriteSheet("assets/hero.png", frame_size=(32, 32))
    idle = sheet.frame(row=0, column=0)
    hero = Sprite(idle, x=-130, y=-79, scale=1.3, layer=2)
    stage.add(hero)
    badge_image = Image.new("RGBA", (30, 30))
    ImageDraw.Draw(badge_image).regular_polygon((15, 15, 14), 5, fill="#ffd479")
    badge = Sprite(badge_image, x=90, y=70, layer=1)
    stage.add(badge)
    person = Puppet.stick_figure(color="#ffd479")
    person.position = (180, -33)
    person.layer = 1
    skeleton = person.skeleton
    standing = skeleton.rest_pose()
    wave_a = standing.with_angles({HumanJoint.RIGHT_ELBOW: -140, HumanJoint.RIGHT_HAND: -40})
    wave_b = standing.with_angles({HumanJoint.RIGHT_ELBOW: -100, HumanJoint.RIGHT_HAND: 30})
    stage.add(person)
    person.act(Script(Puppet).repeat().poses((wave_a, wave_b, wave_a), fps=2))
    tone = Sound("assets/tone.ogg")
    score = 0
    cell_edited = Message[int]("cell edited")

    @stage.on_broadcast(cell_edited)
    def count_edit(event: Event[Stage, int]) -> None:
        amount = event.data
        nonlocal score
        score += amount

    jump = (
        Script(Sprite)
        .glide_by(y=80, seconds=0.3, easing=Ease.OUT)
        .glide_by(y=-80, seconds=0.3, easing=Ease.IN)
    )
    hero.on_key_down(Key.J, jump)

    walking = (
        Script(Sprite)
        .repeat()
        .when(
            Not(KeyDown(Key.RIGHT)),
            then=Script(Sprite).when(
                KeyDown(Key.LEFT),
                then=Script(Sprite).costumes(sheet.frames(), fps=8),
                either=Script(Sprite).set_costume(idle),
            ),
            either=Script(Sprite).costumes(sheet.frames(), fps=8),
        )
    )
    hero.act(walking)

    @stage.on_update
    def update(event: Event[Stage, float]) -> None:
        """Move the hero and derive scrolling from its world position."""
        dt = event.data
        direction = int(stage.keyboard.is_down(Key.RIGHT)) - int(stage.keyboard.is_down(Key.LEFT))
        hero.x = max(-290, min(900, hero.x + direction * 160 * dt))
        stage.camera = (max(0, hero.x - 50), 0)
        background.offset = (-stage.camera[0] * 0.25, 0)
        badge.y = 70 + sin(stage.time * 2) * 12
        badge.direction += 45 * dt

    hero.on_key_down(Key.SPACE, Script(Sprite).play_sound(tone, volume=0.25, wait=False))

    @stage.on_key_down(Key.P)
    def toggle_pause(event: Event[Stage, Key]) -> None:
        """Input callbacks keep working while simulation is paused."""
        if stage.paused:
            stage.resume()
        else:
            stage.pause()

    @stage.on_click
    def edit(event: Event[Stage, Click]) -> None:
        """Convert the screen click into world coordinates, then toggle a cell."""
        position, button = event.data
        if button != MouseButton.LEFT:
            return
        cell = world.cell_at(x=position[0] + stage.camera[0], y=position[1] + stage.camera[1])
        if cell is not None:
            row, column = cell
            tile = None if world.get_tile(row=row, column=column) else "#"
            world.set_tile(row=row, column=column, tile=tile)
            stage.broadcast(cell_edited, 1)
            stage.play(tone, volume=0.2)

    @stage.on_draw
    def draw(canvas: Canvas) -> None:
        """A typed overlay stays fixed while the world scrolls underneath."""
        canvas.text("THE LITTLE WORLD", (-298, 170), size=28, color="#ffd479")
        canvas.text(f"Cells edited: {score}", (-298, 138), size=20)
        canvas.text("Arrows: walk   J: jump   Space: sound   P: pause", (-298, -166), size=20)
        canvas.text("Click near the ground to add or remove tiles.", (-298, -190), size=18)
        if stage.paused:
            canvas.text("PAUSED — press P", (-95, 20), size=26, color="#ffd479")

    stage.run()


if __name__ == "__main__":
    main()
