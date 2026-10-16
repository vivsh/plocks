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
    expected = {
        index for index, line in enumerate(example.read_text().splitlines(), 1) if "# error" in line
    }
    import re

    actual = {
        int(match.group(1)) for match in re.finditer(r"invalid.py:(\d+): error:", result.stdout)
    }
    assert actual == expected, result.stdout
