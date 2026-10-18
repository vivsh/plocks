"""Desktop command working directories and useful command failures."""

import subprocess
import sys
from pathlib import Path


def test_run_custom_entry_from_project_root(tmp_path: Path) -> None:
    """A supporting module and relative asset resolve from the selected game root."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/value.txt").write_text("42")
    (tmp_path / "helper.py").write_text("value=7")
    (tmp_path / "scripts/start.py").write_text(
        "from pathlib import Path\nimport helper\n"
        "assert helper.value == 7\nassert Path('assets/value.txt').read_text() == '42'\n"
        "print('CHILD_CWD_OK')\n"
    )
    (tmp_path / "plocks.toml").write_text('[game]\nentry="scripts/start.py"\n')
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from plocks.cli import main; raise SystemExit(main())",
            "run",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "CHILD_CWD_OK" in result.stdout


def test_run_cli_reports_configuration_error(tmp_path: Path) -> None:
    """A missing entry returns a useful nonzero CLI status without a library traceback."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from plocks.cli import main; raise SystemExit(main())",
            "run",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "main.py" in result.stderr and "Traceback" not in result.stderr


def test_run_uses_main_and_preserves_child_exit_status(tmp_path: Path) -> None:
    """The default entry runs in its project directory and its failure status reaches the shell."""
    (tmp_path / "main.py").write_text(
        "from pathlib import Path\nassert Path('main.py').exists()\nraise SystemExit(7)\n"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from plocks.cli import main; raise SystemExit(main())",
            "run",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 7


def test_cli_exposes_desktop_run_and_bundled_examples() -> None:
    """Help and argument parsing no longer advertise or accept removed web commands."""
    for command in ("--help", "build", "serve"):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from plocks.cli import main; raise SystemExit(main())",
                command,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if command == "--help":
            assert result.returncode == 0 and "{run,examples}" in result.stdout
            assert "serve" not in result.stdout and "build" not in result.stdout
        else:
            assert result.returncode == 2 and "invalid choice" in result.stderr


def test_bad_entry_configuration_does_not_execute_game(tmp_path: Path) -> None:
    """Invalid types, removed settings, escaping paths and malformed config fail before execution."""
    import pytest

    from plocks.cli import _entry

    (tmp_path / "main.py").write_text("raise AssertionError('game must not run')")
    for config in (
        "[game]\nentry = 4\n",
        "[game]\nentry = ''\n",
        "[game]\nentry = '../main.py'\n",
        "[game]\nentry = '/tmp/main.py'\n",
        "[game]\nentry = 'assets'\n",
        "[game]\nassets = []\n",
        "game = 4\n",
        "[game\n",
    ):
        (tmp_path / "plocks.toml").write_text(config)
        with pytest.raises(ValueError):
            _entry(tmp_path)


def test_linked_entry_and_config_are_rejected(tmp_path: Path) -> None:
    """Launch validation rejects symlinked config and entry files without following them."""
    import pytest

    from plocks.cli import _entry

    target = tmp_path / "actual.py"
    target.write_text("pass")
    try:
        (tmp_path / "main.py").symlink_to(target)
    except OSError:
        pytest.skip("Creating symlinks is unavailable")
    with pytest.raises(ValueError, match="symlink"):
        _entry(tmp_path)
    (tmp_path / "main.py").unlink()
    (tmp_path / "main.py").write_text("pass")
    config = tmp_path / "actual.toml"
    config.write_text("[game]\n")
    (tmp_path / "plocks.toml").symlink_to(config)
    with pytest.raises(ValueError, match="symlink"):
        _entry(tmp_path)
