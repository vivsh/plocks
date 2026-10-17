"""Desktop/browser proof of immutable costume operations and shared placement."""

from PIL import Image

from plocks import Canvas, Costume, Joint, Puppet, Skeleton, Sprite, Stage

image = Image.new("RGBA", (3, 2))
for y in range(2):
    for x in range(3):
        image.putpixel((x, y), ((x + 1) * 70, y * 180, 70, 255))
source = Costume(image, anchor=(0.5, 1.5))
left = source.flipped(horizontal=True)
vertical = source.flipped(vertical=True)
quarter = source.rotated(90)
crop = source.cropped(x=1, y=0, width=2, height=1)
anchored = source.with_anchor(x=1.5, y=1)
assert left.anchor == (2.5, 1.5)
assert vertical.anchor == (0.5, 0.5)
assert quarter.anchor == (0.5, 0.5)
assert (quarter.width, quarter.height) == (2, 3)
assert crop.anchor == (-0.5, 1.5)
assert anchored.anchor == (1.5, 1)
assert source.anchor == (0.5, 1.5)
for y in range(2):
    for x in range(3):
        assert left.to_pillow().getpixel((2 - x, y)) == image.getpixel((x, y))
        assert vertical.to_pillow().getpixel((x, 1 - y)) == image.getpixel((x, y))
        assert quarter.to_pillow().getpixel((1 - y, x)) == image.getpixel((x, y))
assert source.resized(width=6, height=6).anchor == (1, 4.5)
assert crop.to_pillow().getpixel((0, 0)) == image.getpixel((1, 0))
assert source.rotated(45).width > source.width
verified = True

stage = Stage(background="midnightblue")
labels = ("Original", "Mirror", "Flip", "Rotate", "Crop", "Anchor")
for index, costume in enumerate((source, left, vertical, quarter, crop, anchored)):
    visual = costume.resized(width=costume.width * 20, height=costume.height * 20)
    actor = Sprite(visual)
    actor.position = (-180 + (index % 3) * 160, 80 - (index // 3) * 150)
    stage.add(actor)
puppet = Puppet(Skeleton({"root": Joint(None)}), parts={"root": quarter.resized(20, 30)})
puppet.position = (200, -120)
stage.add(puppet)


@stage.on_draw
def draw(canvas: Canvas) -> None:
    canvas.text("Costume methods OK", (-220, 160), size=20, color="white")
    for index, label in enumerate(labels):
        canvas.text(label, (-210 + (index % 3) * 160, 15 - (index // 3) * 150), size=18)


if __name__ == "__main__":
    stage.run()
