# 🧱 Build a tiny world

[Home](../index.md) · [Make artwork](index.md)

Paint a world from little square pictures called **tiles**.
Then choose where your hero starts.

**Ready?** Use the `my-game` copy from [Get ready](index.md#get-ready).
Its ground tile and starter map are already prepared.

## 1. Open your world

In Tiled, open `my-game/assets/jungle.tmj`.
This is your map: a grid of **32 × 32** tiles.

## 2. Paint some ground

Select the **Ground** layer. A layer is one sheet of your world.
Choose the ground tile in the Tilesets panel and use the **Stamp Brush**
to paint a few more blocks. Try making three stepping stones.

## 3. Move the starting spot

Select the **Spawns** layer, then the **Select Objects** tool.
Drag the point named **player_start** just above your ground.
That little point marks where the middle of your hero will appear.
Keep its name, including the underscore!

Choose **File → Save**. Keep the name `jungle.tmj`.
Keep `ground.png` beside it: the map uses that picture for its tiles.

## 4. Put the world on screen

Replace your copy's `main.py` with:

```python
from pathlib import Path
from plocks import PixeloramaSheet, Sprite, Stage, TiledMap

assets = Path(__file__).resolve().parent / "assets"
stage = Stage(background="skyblue")

# Put the map's top-left corner on our stage.
level = TiledMap(assets / "jungle.tmj", x=-160, y=64, layer=-1)
for tiles in level.layers.values():
    stage.add(tiles)

# Put our hero at the starting point we chose in Tiled.
art = PixeloramaSheet(assets / "hero.png")
hero = Sprite(art.frames[0])
hero.position = level.points["Spawns/player_start"]
stage.add(hero)

if __name__ == "__main__":
    stage.run()
```

## 5. Look at your creation

Open a terminal in `my-game` and run `python main.py`.
You should see your tiles and your hero at the starting spot.
This little program draws the world; it does not move the hero yet.
The original [Asset Workshop](../../src/plocks/_games/asset_workshop) adds movement and jumps.

**Make it yours:** move `player_start`, save, and restart. Where does the hero appear?

**Stuck?** Keep `Ground`, `Spawns`, and `player_start` spelled as shown.
If the map cannot find its picture, check that `ground.png` is still in `assets`.

Want your hero to fall and land? Try [jumping and landing](../activities/physics.md).
Drawing a map puts pictures on screen; gravity needs `Stage(physics=True)` and
solid tiles too.
