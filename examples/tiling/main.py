"""Three tile types, generated with Pillow. Click a cell to change its tile."""

from PIL import Image, ImageDraw

from plocks import Canvas, MouseButton, Point, Stage, TileMap


def main() -> None:
    """Draw grass, dirt and stone; left-click cycles tiles, right-click clears."""
    stage = Stage(width=640, height=400, background="midnightblue")

    grass = Image.new("RGBA", (32, 32), "forestgreen")
    grass_art = ImageDraw.Draw(grass)
    grass_art.rectangle((0, 0, 31, 5), fill="limegreen")
    for x in (5, 15, 25):
        grass_art.line((x, 18, x + 2, 12), fill="yellowgreen", width=2)

    dirt = Image.new("RGBA", (32, 32), "saddlebrown")
    dirt_art = ImageDraw.Draw(dirt)
    for x, y in ((5, 7), (21, 5), (13, 19), (26, 26)):
        dirt_art.rectangle((x, y, x + 3, y + 2), fill="peru")

    stone = Image.new("RGBA", (32, 32), "slategray")
    stone_art = ImageDraw.Draw(stone)
    stone_art.rectangle((0, 0, 31, 31), outline="darkslategray", width=2)
    stone_art.line((0, 16, 31, 16), fill="darkslategray", width=2)
    stone_art.line((16, 0, 16, 16), fill="darkslategray", width=2)
    stone_art.line((8, 16, 8, 31), fill="darkslategray", width=2)

    world = TileMap(
        rows=[
            "............",
            "............",
            "....SS......",
            "....SS......",
            "..GGGG..GG..",
            "GGDDDDGGDDGG",
            "DDDDDDDDDDDD",
            "SSSSSSSSSSSS",
        ],
        palette={"G": grass, "D": dirt, "S": stone},
        tile_size=(40, 40),
        x=-240,
        y=140,
    )
    stage.add(world)

    @stage.on_click
    def edit(position: Point, button: MouseButton) -> None:
        cell = world.cell_at(
            x=position[0] + stage.camera[0],
            y=position[1] + stage.camera[1],
        )
        if cell is None:
            return
        row, column = cell
        if button is MouseButton.RIGHT:
            world.set_tile(row=row, column=column, tile=None)
        elif button is MouseButton.LEFT:
            tiles = (None, "G", "D", "S")
            current = world.get_tile(row=row, column=column)
            next_tile = tiles[(tiles.index(current) + 1) % len(tiles)]
            world.set_tile(row=row, column=column, tile=next_tile)

    @stage.on_draw
    def instructions(canvas: Canvas) -> None:
        canvas.text("Click: grass > dirt > stone > empty", (-280, 185), size=24)
        canvas.text("Right-click to erase a tile", (-280, 160), size=20)

    stage.run()


if __name__ == "__main__":
    main()
