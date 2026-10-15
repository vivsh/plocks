"""Incorrect teaching examples must produce specific, useful static diagnostics."""

import subprocess
import sys
from pathlib import Path


def test_negative_examples(tmp_path: Path) -> None:
    """Callbacks, assets, coordinates, and pose angle mistakes are all rejected by mypy."""
    fixture = Path(__file__).parent / "typing/invalid.txt"
    example = tmp_path / "invalid.py"
    example.write_bytes(fixture.read_bytes())
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", str(example)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout.count("error:") == 35, result.stdout
    assert "on_update" in result.stdout and "on_draw" in result.stdout
    assert "Sprite" in result.stdout and "assignment" in result.stdout
    assert '"on_start" of "Puppet"' in result.stdout
    assert '"on_message" of "Sprite"' in result.stdout
