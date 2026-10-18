from PIL import Image, ImageDraw

from plocks import Canvas, Click, Event, Key, Sound, Sprite, Stage


def main() -> None:
    """Move the Pillow sprite with arrows; press Space or click to play a tone."""
    stage = Stage(background="#102033")
    picture = Image.new("RGBA", (40, 40))
    ImageDraw.Draw(picture).rounded_rectangle((0, 0, 39, 39), radius=8, fill="#ffb454")
    hero = Sprite(picture)
    stage.add(hero)
    tone = Sound("assets/tone.ogg")
    sounds = 0

    @stage.on_update
    def update(event: Event[Stage, float]) -> None:
        """Move at 100 world pixels per simulated second."""
        dt = event.data
        if stage.keyboard.is_down(Key.RIGHT):
            hero.x += 100 * dt
        if stage.keyboard.is_down(Key.LEFT):
            hero.x -= 100 * dt

    def play_tone_now() -> None:
        """Start one independent OGG occurrence after input."""
        nonlocal sounds
        stage.play(tone, volume=0.3)
        sounds += 1

    @stage.on_key_down(Key.SPACE)
    def play_tone(event: Event[Stage, Key]) -> None:
        play_tone_now()

    @stage.on_click
    def clicked(event: Event[Stage, Click]) -> None:
        """Place the hero at the clicked location and play a tone."""
        position, _button = event.data
        hero.position = position
        play_tone_now()

    @stage.on_draw
    def draw(canvas: Canvas) -> None:
        """Draw a score overlay unaffected by world camera movement."""
        canvas.text("Arrows move. Space / click plays sound.", (-220, 155), size=20)
        canvas.text(f"Sounds: {sounds}    x: {hero.x:.0f}", (-220, 125), size=20)

    stage.run()


if __name__ == "__main__":
    main()
