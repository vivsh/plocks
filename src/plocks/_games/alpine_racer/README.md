# Alpine Racer

Race five cars along a winding mountain route. You have **five minutes** to
get as far ahead as you can. Bumps and grass slow you down. Tree trunks stop the car: steer away to keep racing.

```sh
plocks run alpine_racer
```

**Up / W:** accelerate · **Down / S:** brake · **Left / Right / A / D:** steer
**P:** pause · **R:** restart

With a controller, use the left stick to steer, A or the right trigger to
accelerate, and B or the left trigger to brake. Start pauses; Select restarts.
The clock begins when you first accelerate. Pausing stops the clock too.
Fast bends push the car outward: steer into the turn, or brake before a tight corner.
The tightest corners need braking at full speed.
On grass you can still crawl forward or steer back onto the road, even when stopped.
You cannot drive through tree trunks, but their branches do not block the road.

## Make it yours

```sh
plocks examples alpine_racer --copy-to my-racer
cd my-racer
python main.py
```

1. Change `TOP_SPEED` to change your maximum speed; lower the rival speeds too for a slower race.
2. Change `RACE_SECONDS` from 300 to 60 for a quick practice round.
3. Find the five cruising speeds in `reset()` and make one rival faster.
4. Replace the orange car pictures. Keep all three the same image size.
5. Lower `CORNER_PUSH` for easier corners, or raise it for more outward drift.

## Read it in small steps

- **Setup** loads ready-made pictures and makes the cars, trees and road strips.
- **`update`** reads controls, changes speed and distance, and checks for bumps.
- **`reset`** puts the racers back without adding more scenery.
- **`draw`** shows the position and time. Those words stay on the screen.
- **`project`** is the trickier part: faraway things look smaller and nearer the horizon.

This is a 2D game that looks 3D. A stack of thin picture strips makes the road.
`show_road()` moves those strips sideways for bends and changes the markings as
you advance. Trees and rivals grow as you approach. The camera and physics stay
at their defaults; the perspective code chooses the picture positions.

The orange car changes between straight, left and right pictures when you steer.
Each rival stores its Sprite, lane, travelled distance and cruising speed in a tuple.
You can change the driving rules before learning the perspective maths.

The speed display is in km/h. `UNITS_PER_METRE` sets how quickly pictures rush past;
raising it makes the sense of speed stronger without changing the five-minute timer.

The small **ROUTE** preview draws the same bends as the road, from START on the
left to FINISH on the right. Orange is your car; blue dots are the rivals. Each
lap repeats this route. The preview keeps the road's proportions rather than
drawing a pretend oval circuit.
