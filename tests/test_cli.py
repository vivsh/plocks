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


def test_build_cli_reports_configuration_error(tmp_path: Path) -> None:
    """A missing entry returns a useful nonzero CLI status without a library traceback."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from plocks.cli import main; raise SystemExit(main())",
            "build",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "main.py" in result.stderr and "Traceback" not in result.stderr
