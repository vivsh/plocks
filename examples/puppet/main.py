"""A generated human uses the same image-part renderer as custom Puppets."""

from plocks import HumanJoint, Loop, Poses, Puppet, Stage

stage = Stage(background="midnightblue")
person = Puppet.stick_figure(color="gold")
stage.add(person)
rest = person.skeleton.rest_pose()
raised = rest.with_angles({HumanJoint.RIGHT_SHOULDER: -120, HumanJoint.RIGHT_ELBOW: -60})
person.act(Loop(Poses((rest, raised, rest), fps=2)))
stage.run()
