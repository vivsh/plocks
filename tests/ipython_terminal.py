"""Exercise the public API in a real terminal; also used against installed wheels."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections.abc import Callable
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pexpect


def exercise(
    root: Path, *, native: bool = False, installed: bool = False, simple: bool = False
) -> None:
    """Check live prompt editing, script/input timing, error recovery and interpreter exit."""
    import pexpect

    root.mkdir(parents=True, exist_ok=True)
    (root / "assets").mkdir(exist_ok=True)
    (root / "assets/hero.png").write_bytes(
        files("plocks").joinpath("_games/platformer/assets/hero.png").read_bytes()
    )
    environment = {
        **os.environ,
        "IPYTHONDIR": str(root / "profile"),
        "SDL_AUDIODRIVER": "dummy",
        "PYGAME_HIDE_SUPPORT_PROMPT": "1",
        "PROMPT_TOOLKIT_NO_CPR": "1",
        "TERM": "xterm-256color",
    }
    if native:
        environment.pop("SDL_VIDEODRIVER", None)
    else:
        environment["SDL_VIDEODRIVER"] = "dummy"
    arguments = [
        "-m",
        "IPython",
        "--no-banner",
        "--colors=NoColor",
        "--HistoryManager.enabled=False",
        "--TerminalInteractiveShell.confirm_exit=False",
    ]
    if simple:
        arguments.append("--simple-prompt")
    child: pexpect.spawn[str] = pexpect.spawn(
        sys.executable, arguments, env=environment, cwd=str(root), encoding="utf-8", timeout=15
    )
    prompt = r"In \[\d+\]:"
    counter = 0
    with (root / "terminal.txt").open("w", encoding="utf-8") as log:
        child.logfile_read = log

        def command(code: str) -> None:
            """Wait for executed output, never mistake echoed source for an assertion passing."""
            nonlocal counter
            counter += 1
            if "\n" in code:
                code = f"exec({code!r})"
            child.sendline(code + f'; print("PLOCKS_" + "CHECK_{counter}")')
            child.expect_exact(f"PLOCKS_CHECK_{counter}\r\n")
            output = child.before or ""
            assert "Traceback (most recent call last)" not in output, output
            child.expect(prompt)

        try:
            child.expect(prompt)
            command(
                "from pathlib import Path; from importlib.resources import files; "
                "from plocks import Stage, Sprite, Puppet, Key, Event, Sound, Message, StageError; "
                "import plocks, pygame, threading, atexit"
            )
            if installed:
                command('assert Path(plocks.__file__).parent.parent.name == "site-packages"')
            if simple:
                _simple_prompt(command)
            else:
                _readme_example(command)
                _live_game(command, child)
            child.sendline("exit")
            child.expect(pexpect.EOF)
            child.close()
            assert child.exitstatus == 0
        finally:
            if child.isalive():
                child.terminate(force=True)
    output = (root / "terminal.txt").read_text()
    for unexpected in (
        "Task exception was never retrieved",
        "Task was destroyed",
        "was never awaited",
        "Exception in callback",
        "Exception ignored in atexit callback",
    ):
        assert unexpected not in output, output
    if not simple:
        assert "ValueError: IPYTHON_GAME_FAILURE" in output
        assert (root / "exit-cleanup.txt").read_text() == "clean"
    (root / "results.json").write_text(
        json.dumps(
            {
                "python": sys.version,
                "ipython": version("ipython"),
                "pygame_ce": version("pygame-ce"),
                "pillow": version("pillow"),
                "readme_snippets_executed": not simple,
                "native": native,
                "installed": installed,
                "simple_prompt_rejected": simple,
                "public_api_checks": counter,
                "passed": True,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"IPYTHON_TERMINAL_OK: {counter} checks, native={native}, installed={installed}")


def _readme_example(command: Callable[[str], None]) -> None:
    """Execute both actual README Python snippets with their documented relative asset path."""
    readme = Path(__file__).parents[1] / "README.md"
    section = (
        readme.read_text().split("## 🔬 Try ideas live with IPython", 1)[1].split("\n## ", 1)[0]
    )
    programs = re.findall(r"```python\n(.*?)```", section, re.DOTALL)
    assert len(programs) == 2
    for program in programs:
        command(program.strip())
    time.sleep(1.2)
    command("assert stage.running and hero.x==0; stage.pause(); frozen=stage.time")
    time.sleep(0.1)
    command("assert stage.time==frozen; stage.resume(); stage.stop(); assert stage._task is None")


def _simple_prompt(command: Callable[[str], None]) -> None:
    """Real --simple-prompt sessions reject interactive startup before native acquisition."""
    command("stage = Stage()")
    command(
        "try:\n"
        "    stage.run(interactive=True)\n"
        "except StageError:\n"
        "    assert stage._state == 'new' and not pygame.display.get_init()\n"
        "else:\n"
        "    raise AssertionError('simple prompt must be rejected')"
    )


def _live_game(command: Callable[[str], None], child: pexpect.spawn[str]) -> None:
    """Drive independent actors, key scripts, audio, live edits and normal/error shutdown."""
    command(
        "stage=Stage(background='midnightblue'); "
        "hero=Sprite(files('plocks').joinpath('_games/platformer/assets/hero.png')); "
        "friend=Puppet.stick_figure(); friend.position=(-100,30); "
        "stage.add(hero); stage.add(friend); main_thread=threading.get_ident(); starts=[]"
    )
    command(
        "@friend.on_update\n"
        "def walk(event: Event[Puppet,float]) -> None:\n"
        "    assert threading.get_ident()==main_thread\n"
        "    friend.x += 60*event.data\n"
        "@stage.on_start\n"
        "def started(event: Event[Stage,None]) -> None:\n"
        "    starts.append(1)"
    )
    command("stage.run(interactive=True); assert stage.running; driver=stage._task")
    time.sleep(0.2)
    command("assert starts==[1] and friend.x>-95 and stage.time>0")
    command("hero.x=0; motion=hero.glide_by(x=60,seconds=.15); hero.say('Hello!',seconds=.1)")
    time.sleep(0.3)
    command("assert motion.done and hero.x==60 and hero._bubble is None")
    command(
        "hop=hero.sequence(); hop.glide_by(y=40,seconds=.1); "
        "hop.wait(.35); hop.glide_by(y=-40,seconds=.1); hero.on_key_down(Key.SPACE,hop)"
    )
    command("pygame.event.post(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_SPACE))")
    time.sleep(0.1)
    command("assert hero.y>0")
    time.sleep(0.55)
    command("assert hero.y==0 and not stage._actions; assert stage.keyboard.is_down(Key.SPACE)")
    command("pygame.event.post(pygame.event.Event(pygame.WINDOWFOCUSLOST))")
    time.sleep(0.1)
    command("assert not stage.paused and not stage.keyboard.is_down(Key.SPACE)")
    command("points=Message[int]('points'); received=[]")
    command(
        "@hero.on_broadcast(points)\n"
        "def scored(event: Event[Sprite,int]) -> None:\n"
        "    received.append(event.data)"
    )
    command("stage.broadcast(points,3)")
    time.sleep(0.1)
    command("assert received==[3]; stage.pause(); frozen=stage.time; still=friend.position")
    time.sleep(0.1)
    command("assert stage.time==frozen and friend.position==still; stage.resume()")
    time.sleep(0.1)
    command(
        "assert stage.time>frozen; voice=stage.play("
        "Sound(files('plocks').joinpath('_games/dino_run/assets/pop.ogg')),loop=True)"
    )
    # Ctrl-C cancels the partially edited command, while the game keeps its own driver.
    child.send("hero.x = 999")
    time.sleep(0.1)
    child.sendcontrol("c")
    command("assert stage.running and hero.x==60")
    command(
        "stage.stop(); assert driver.done() and stage._task is None and not stage.objects; "
        "assert hero._stage is None and friend._stage is None and voice.finished; "
        "assert not pygame.display.get_init() and not pygame.mixer.get_init()"
    )
    command(
        "stage=Stage(); stage.run(interactive=True); never_started=stage._task; "
        "stage.stop(); assert never_started.done() and stage._task is None"
    )
    command("stage=Stage(); stage.run(interactive=True); canceled=stage._task; canceled.cancel()")
    time.sleep(0.1)
    command("assert canceled.cancelled() and stage._task is None and stage._target is None")
    command("stage=Stage()")
    command(
        "@stage.on_update\n"
        "def broken(event: Event[Stage,float]) -> None:\n"
        "    raise ValueError('IPYTHON_GAME_FAILURE')"
    )
    command("stage.run(interactive=True); failed=stage._task")
    time.sleep(0.1)
    # Consume the asynchronous traceback separately; errors must not vanish into a task.
    child.expect(r"ValueError: IPYTHON_GAME_FAILURE")
    command(
        "assert failed.done() and isinstance(failed.exception(),ValueError); "
        "assert stage._task is None and stage._target is None"
    )
    command(
        "stage=Stage(); stage.run(interactive=True); closed=stage._task; "
        "pygame.event.post(pygame.event.Event(pygame.QUIT))"
    )
    time.sleep(0.1)
    command("assert closed.done() and closed.exception() is None; assert stage._target is None")
    command("stage=Stage(); exiting=[]")
    command(
        "def check_exit(owner=stage, tasks=exiting, display=pygame.display, "
        "output=Path('exit-cleanup.txt').resolve()) -> None:\n"
        "    assert owner._task is None and owner._target is None\n"
        "    assert tasks[0].done() and not display.get_init()\n"
        "    output.write_text('clean')\n"
        "atexit.register(check_exit)"
    )
    command("stage.run(interactive=True); exiting.append(stage._task)")


def main() -> None:
    """Run an isolated terminal with an optional retained validation output folder."""
    if sys.platform == "win32":
        print("POSIX pseudo-terminal required; Windows lifecycle tests run through pytest")
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--simple", action="store_true")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="plocks-ipython-") as temporary:
        exercise(
            args.output or Path(temporary),
            native=args.native,
            installed=args.installed,
            simple=args.simple,
        )


if __name__ == "__main__":
    main()
