from plocks import HumanJoint, Puppet, Script, Stage


def main() -> None:
    """A generated human uses the same image-part renderer as custom Puppets."""
    stage = Stage(background="midnightblue")
    person = Puppet.stick_figure(color="gold")
    stage.add(person)
    rest = person.skeleton.rest_pose()
    raised = rest.with_angles({HumanJoint.RIGHT_SHOULDER: -120, HumanJoint.RIGHT_ELBOW: -60})
    person.act(Script(Puppet).repeat().call(Script(Puppet).poses((rest, raised, rest), fps=2)))
    stage.run()


if __name__ == "__main__":
    main()
