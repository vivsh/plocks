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


def test_negative_examples_pyright(tmp_path: Path) -> None:
    """Pyright rejects the same wrong actors, payloads, callbacks and public awaits."""
    import json

    example = tmp_path / "invalid.py"
    example.write_bytes((Path(__file__).parent / "typing/invalid.txt").read_bytes())
    result = subprocess.run(
        [sys.executable, "-m", "pyright", "--outputjson", str(example)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    diagnostics = json.loads(result.stdout)["generalDiagnostics"]
    expected = {
        index for index, line in enumerate(example.read_text().splitlines(), 1) if "# error" in line
    }
    # Deliberately invalid snippets share setup imports; unused-import lint is not
    # an API typing diagnostic and is checked separately on valid source.
    actual = {
        item["range"]["start"]["line"] + 1
        for item in diagnostics
        if item["severity"] == "error" and item.get("rule") != "reportUnusedImport"
    }
    assert actual == expected, result.stdout
