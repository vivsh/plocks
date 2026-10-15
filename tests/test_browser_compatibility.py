"""Pinned native ABI guardrails and consistency of transformed wheel metadata."""

import base64
import csv
import hashlib
import io
import zipfile
from pathlib import Path

import pytest

from plocks import BuildError
from plocks.web import _pillow


def test_unknown_native_module_is_rejected() -> None:
    """A new or damaged upstream binary cannot receive offsets intended for the pinned module."""
    with pytest.raises(BuildError, match="review runtime compatibility"):
        _pillow._patch_webp(b"a different native module")


def test_corrected_wheel_record_and_repeatability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wheel rewriting changes only the selected payload and RECORD, preserving install integrity."""
    wheel = tmp_path / "pillow.whl"
    member = _pillow._MEMBER
    record = "pillow-11.3.0.dist-info/RECORD"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(member, b"original native fixture")
        archive.writestr("PIL/__init__.py", b"unchanged")
        archive.writestr(record, f"{member},sha256=old,23\nPIL/__init__.py,,\n{record},,\n")
    monkeypatch.setattr(_pillow, "_patch_webp", lambda body: b"corrected native fixture")
    _pillow._patch_wheel(wheel)
    first = wheel.read_bytes()
    with zipfile.ZipFile(wheel) as archive:
        corrected = archive.read(member)
        assert corrected == b"corrected native fixture"
        assert archive.read("PIL/__init__.py") == b"unchanged"
        rows = {row[0]: row[1:] for row in csv.reader(io.StringIO(archive.read(record).decode()))}
        digest = base64.urlsafe_b64encode(hashlib.sha256(corrected).digest()).rstrip(b"=").decode()
        assert rows[member] == ["sha256=" + digest, str(len(corrected))]
        assert rows[record] == ["", ""]
    _pillow._patch_wheel(wheel)
    assert wheel.read_bytes() == first
