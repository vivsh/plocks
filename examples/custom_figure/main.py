"""A rigged arm: each image rotates around its attachment pivot."""

from PIL import Image, ImageDraw

from plocks import Costume, Joint, Loop, Poses, Puppet, Skeleton, Stage

stage = Stage(background="#122338")
skeleton = Skeleton({"shoulder": Joint(None), "elbow": Joint("shoulder", (0, -65))})
upper = Image.new("RGBA", (16, 73))
ImageDraw.Draw(upper).rounded_rectangle((1, 1, 14, 71), radius=6, fill="orange")
forearm = Image.new("RGBA", (14, 63))
ImageDraw.Draw(forearm).rounded_rectangle((1, 1, 12, 61), radius=5, fill="gold")
arm = Puppet(
    skeleton,
    parts={
        "shoulder": Costume(upper, anchor=(8, 4)),
        "elbow": Costume(forearm, anchor=(7, 4)),
    },
)
arm.y = 60
stage.add(arm)
rest = skeleton.rest_pose()
bent = rest.with_angles({"shoulder": -30, "elbow": -100})
arm.act(Loop(Poses((rest, bent, rest), fps=1)))
stage.run()
