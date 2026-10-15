"""A pinned ABI correction for Pillow 11.3.0's wasm WebP NOARGS callbacks.

CPython passes (self, NULL), but three callbacks have a one-argument wasm type.
Use the two-i32-argument type already present in the module. For get_info and
get_next, replace the first zero-initialized i32 scratch local with the NULL
argument, keeping all local indexes and code/data relocations unchanged. reset
has no scratch locals. Neither instructions nor section sizes move.

Upstream declarations: python-pillow/Pillow, tag 11.3.0, src/_webp.c.
Only the exact inspected artifact is accepted. This is a build-time correction;
game execution has no compatibility wrapper or retained decoding cache.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import os
import zipfile
from pathlib import Path

from ..errors import BuildError

_PATCH_ID = "pillow-11.3.0-webp-noargs-v1"
_MEMBER = "PIL/_webp.cpython-312-wasm32-emscripten.so"
_SOURCE_SHA256 = "c73390597ff47f14ec5fe868de9fe05586538947bd9e060e1a9b55e1014dafc5"
_PATCHED_SHA256 = "b596e4e323a4f7add954ae7fb780e3f1ef4359aaec683e1df7b70d7d97c66bba"
_CHANGES = ((1893, 6, 0), (1895, 6, 0), (1896, 6, 0), (11426, 2, 1), (11614, 3, 2))


def _patch_webp(body: bytes) -> bytes:
    """Correct five bytes of the exact pinned wasm module, checking both identities."""
    digest = hashlib.sha256(body).hexdigest()
    if digest == _PATCHED_SHA256:
        return body
    if digest != _SOURCE_SHA256:
        raise BuildError(
            "Unexpected Pillow WebP module; review runtime compatibility before building"
        )
    corrected = bytearray(body)
    for offset, before, after in _CHANGES:
        if corrected[offset] != before:
            raise BuildError("Pillow WebP callback layout changed")
        corrected[offset] = after
    result = bytes(corrected)
    if hashlib.sha256(result).hexdigest() != _PATCHED_SHA256:
        raise BuildError("Pillow WebP ABI correction did not produce the pinned result")
    return result


def _record(body: bytes, corrected: bytes) -> bytes:
    """Update the wheel's RECORD for its modified native module; preserve other rows."""
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    found = False
    for row in csv.reader(io.StringIO(body.decode("utf-8"))):
        if row[0] == _MEMBER:
            digest = base64.urlsafe_b64encode(hashlib.sha256(corrected).digest()).rstrip(b"=")
            row[1:] = ["sha256=" + digest.decode("ascii"), str(len(corrected))]
            found = True
        writer.writerow(row)
    if not found:
        raise BuildError("Pillow wheel RECORD does not describe its WebP module")
    return output.getvalue().encode("utf-8")


def _patch_wheel(wheel: Path) -> None:
    """Correct staged Pillow and its wheel metadata, including the local index fallback."""
    temporary = wheel.with_suffix(".corrected")
    with zipfile.ZipFile(wheel) as original:
        if _MEMBER not in original.namelist():
            raise BuildError("Pinned Pillow wheel is missing its WebP module")
        corrected = _patch_webp(original.read(_MEMBER))
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as output:
            for name in sorted(original.namelist()):
                body = original.read(name)
                if name == _MEMBER:
                    body = corrected
                elif name.endswith(".dist-info/RECORD"):
                    body = _record(body, corrected)
                info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                output.writestr(info, body)
    os.replace(temporary, wheel)
