"""An enemy patrols between walls and uses a ray to look for the player."""

from plocks import (
    Canvas,
    Event,
    Image,
    Key,
    Label,
    Sprite,
    Stage,
    TileMap,
)

stage = Stage(width=480, height=360, physics=True, background="midnightblue")
player = stage.gamepads[0]
player.map_left_stick(left=Key.LEFT, right=Key.RIGHT)
world = TileMap(
    ["#.............#"] * 8 + ["###############"],
    {"#": Image.rectangle(32, 32, color="slategray")},
    tile_size=(32, 32),
    solid={"#"},
    x=-240,
    y=136,
)
stage.add(world)
hero = Sprite(Image.rectangle(20, 32, color="orange"), x=-120, y=-104)
enemy = Sprite(Image.rectangle(20, 32, color="skyblue"), x=40, y=-104)
for actor in (hero, enemy):
    stage.add(actor)
    actor.body.rotation_locked = True
hint = Label("Arrows: walk. The blue enemy checks ahead.", position=(0, 150), size=18)
stage.add(hint)


@stage.on_update
def update(event: Event[Stage, float]) -> None:
    hero.body.velocity = (player.left_stick[0] * 120, hero.body.velocity[1])
    # Check the next step, plus two extra pixels. Keep the original direction
    # when the way is clear; turn around when a wall or the hero blocks it.
    if enemy.body.grounded:
        if not enemy.body.can_travel(distance=80 * event.data + 2):
            enemy.direction = (enemy.direction + 180) % 360
        enemy.body.travel_along(speed=80)
    # The ray ignores its owner. A hit on the hero means no wall is in the way.
    hit = stage.physics.raycast(enemy.position, hero.position, ignore=(enemy,))
    sees_hero = hit is not None and hit.target is hero and enemy.distance_to(hero) < 180
    hint.text = "I see you!" if sees_hero else "Arrows: walk. The enemy checks ahead."


@stage.on_draw
def draw(canvas: Canvas) -> None:
    # A fixed camera makes world coordinates and overlay coordinates coincide.
    canvas.line(enemy.position, hero.position, color="gold", width=1)


if __name__ == "__main__":
    stage.run()
