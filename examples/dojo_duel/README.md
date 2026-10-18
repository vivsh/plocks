# 🥋 Dojo Duel

Two players share one keyboard in a colourful martial-arts match.

```sh
plocks run examples/dojo_duel
```

**Blue:** A / D move · W jump · F punch · G kick

**Ruby:** Left / Right move · Up jump · K punch · L kick

**R:** start another round

## What you'll learn

- **Two players:** Each fighter has its own keys and health.
- **Scripts:** A punch changes costume, waits for its hit moment, then stands again.
- **Functions:** `hit` is one shared job for health, push-back and the impact flash.
- **Numbers and `if`:** An attack only lands when the other fighter is close enough.

## Make it yours

1. Change `damage=12` to make punches stronger or gentler.
2. Change `reach=145` in `blue_punch_hit` to make a longer punch.
3. Add a new script using the middle and last costumes in the asset sheets.

The fighters and moonlit dojo are original artwork made for this example. Copy the
whole folder, including `assets/`, into your own project to change it.
