"""Assemble static websites without evaluating game scripts or changing assets."""

from __future__ import annotations

import hashlib
import html
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from importlib.resources import files
from pathlib import Path

from ..errors import BuildError
from ._pillow import _MEMBER, _PATCH_ID, _PATCHED_SHA256, _SOURCE_SHA256, _patch_wheel
from .collect import check_source, collect
from .project import ProjectConfig, _is_link, load_project
from .runtime import artifacts, download, extract_wheel


def _launcher(entry: Path) -> str:
    return f'''"""Generated launcher; project code runs only in the player."""
import os
import runpy
import sys
import traceback
from pathlib import Path
import pygame
from PIL import Image

root = Path(__file__).parent / "game"
os.chdir(root)
sys.path.insert(0, str(root))
sys.path.insert(0, str((root / {entry.as_posix()!r}).parent))
try:
    runpy.run_path({entry.as_posix()!r}, run_name="__main__")
except Exception:
    import platform
    platform.window.plocksError(traceback.format_exc())
    raise
'''


def _stage(config: ProjectConfig, paths: tuple[Path, ...], staging: Path) -> None:
    """Copy selected sources and the installed pure-Python framework into staging."""
    for path in paths:
        target = staging / "game" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(config.root / path, target)
    package = Path(__file__).resolve().parents[1]
    shutil.copytree(
        package, staging / "plocks", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    (staging / "main.py").write_text(_launcher(config.entry), encoding="utf-8")


def _package(staging: Path, downloaded: Path) -> Path:
    """Use pinned Pygbag solely for packing; its cache stays within temporary staging."""
    try:
        version = importlib.metadata.version("pygbag")
    except importlib.metadata.PackageNotFoundError as error:
        raise BuildError(
            "Install browser tools with: python -m pip install 'plocks[web]'"
        ) from error
    if version != "0.9.3":
        raise BuildError(f"This runtime requires pygbag==0.9.3; found {version}")
    template = downloaded / "blank.tmpl"
    template.write_text("<!doctype html>", encoding="utf-8")
    command = [
        sys.executable,
        "-m",
        "pygbag",
        "--build",
        "--no_opt",
        "--PYBUILD",
        "3.12",
        "--template",
        str(template),
        "--icon",
        str(downloaded / "0.9.3/favicon.png"),
        str(staging),
    ]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    if result.returncode:
        raise BuildError(
            f"Pygbag packaging failed:\n{result.stdout[-4000:]}\n{result.stderr[-4000:]}"
        )
    archives = list((staging / "build/web").glob("*.apk"))
    if len(archives) != 1:
        raise BuildError("Pygbag did not produce exactly one game archive")
    return archives[0]


def _normalized_zip(source: Path, destination: Path) -> None:
    """Archive files deterministically with safe relative names and stable modes."""
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(path.relative_to(source).as_posix(), (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())


def _normalize_apk(source: Path, target: Path) -> None:
    with (
        zipfile.ZipFile(source) as original,
        zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output,
    ):
        for name in sorted(original.namelist()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            output.writestr(info, original.read(name))


def _website(config: ProjectConfig, packed: Path, downloaded: Path, website: Path) -> None:
    """Create the host-independent page and either remote or local runtime URLs."""
    website.mkdir()
    cdn = "https://pygame-web.github.io/cdn/0.9.3/"
    if config.runtime_mode == "self-contained":
        cdn = "runtime/cdn/0.9.3/"
        for artifact in artifacts():
            if not artifact[0].endswith((".whl", ".tmpl")):
                target = website / "runtime/cdn" / artifact[0]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(downloaded / artifact[0], target)
    template = files(__package__).joinpath("templates/site.html").read_text()
    template = template.replace("@@TITLE@@", html.escape(config.title)).replace("@@CDN@@", cdn)
    (website / "index.html").write_text(template, encoding="utf-8")
    for name in ("site.css", "site.js"):
        content = (
            files(__package__).joinpath(f"templates/{name}").read_text().replace("@@CDN@@", cdn)
        )
        (website / name).write_text(content, encoding="utf-8")
    shutil.copyfile(downloaded / "0.9.3/favicon.png", website / "favicon.png")
    shutil.copyfile(downloaded / "support/browserfs.min.js", website / "browserfs.min.js")
    (website / "runtime-index").mkdir()
    index = json.loads((downloaded / "index-0.9.3-cp312.json").read_text())
    local_index = {name: index[name] for name in ("-CDN-", "pygame", "PIL")}
    local_index["typing_extensions"] = "pure/typing_extensions-4.16.0-py3-none-any.whl"
    (website / "runtime-index/index-0.9.3-cp312.json").write_text(
        json.dumps(local_index, sort_keys=True), encoding="utf-8"
    )
    for wheel in downloaded.rglob("*.whl"):
        target = website / "runtime-index" / wheel.relative_to(downloaded)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(wheel, target)
    _normalize_apk(packed, website / "game.apk")
    _notices(website, downloaded)
    _manifest(config, website)


def _notices(website: Path, downloaded: Path) -> None:
    notices = website / "notices"
    notices.mkdir()
    if (downloaded / "notices").is_dir():
        shutil.copytree(downloaded / "notices", notices, dirs_exist_ok=True)
    for wheel in downloaded.rglob("*.whl"):
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                if any(
                    word in Path(name).name.lower() for word in ("license", "copying", "notice")
                ):
                    (notices / (wheel.stem + "-" + Path(name).name)).write_bytes(archive.read(name))
    (notices / "README.txt").write_text(
        "Runtime: Pygbag 0.9.3 (MIT), CPython 3.12 (PSF), pygame-ce 2.5.7 (LGPL-2.1-or-later), Pillow 11.3.0 (MIT-CMU).\n"
        "pygame/freesansbold.ttf: Copyright 2002 Free Software Foundation. Unmodified GNU GPL font; see GNU-GPL-2.0.txt.\n"
        "Additional runtime-library notices are included alongside this file.\n"
        "Pillow's wasm WebP module has three NOARGS callback signatures corrected at build time.\n"
        "The original license remains applicable; build-manifest.json identifies this modification.\n"
        "Sources: https://github.com/pygame-web/pygbag and https://github.com/pygame-web/cdn\n"
        "https://github.com/pygame-community/pygame-ce https://github.com/python/cpython https://github.com/python-pillow/Pillow\n",
        encoding="utf-8",
    )


def _manifest(config: ProjectConfig, website: Path) -> None:
    inventory = [
        {
            "path": path.relative_to(website).as_posix(),
            "size": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(website.rglob("*"))
        if path.is_file()
    ]
    document = {
        "plocks": importlib.metadata.version("plocks"),
        "mode": config.runtime_mode,
        "python": "3.12",
        "pygbag": "0.9.3",
        "pygame-ce": "2.5.7",
        "Pillow": "11.3.0",
        "compatibility": [
            {
                "id": _PATCH_ID,
                "path": _MEMBER,
                "input_sha256": _SOURCE_SHA256,
                "output_sha256": _PATCHED_SHA256,
            }
        ],
        "files": inventory,
        "runtime": [
            dict(zip(("path", "url", "size", "sha256"), artifact)) for artifact in artifacts()
        ],
    }
    (website / "build-manifest.json").write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _publish(website: Path, archive: Path, dist: Path) -> None:
    """Replace owned outputs; preserve old artifacts if filesystem rollback also fails."""
    dist.mkdir(exist_ok=True)
    replacements = ((website, dist / "web"), (archive, dist / "game-web.zip"))
    backup = Path(tempfile.mkdtemp(prefix=".plocks-backup-", dir=dist))
    moved: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    try:
        for source, target in replacements:
            if _is_link(target):
                raise BuildError(f"Output must not be a symlink or junction: {target}")
            if target.exists():
                saved = backup / target.name
                os.replace(target, saved)
                moved.append((saved, target))
            os.replace(source, target)
            installed.append(target)
    except BaseException:
        try:
            for target in reversed(installed):
                shutil.rmtree(target) if target.is_dir() else target.unlink()
            for saved, target in reversed(moved):
                os.replace(saved, target)
        except OSError as error:
            raise BuildError(
                f"Cannot restore outputs; previous artifacts are preserved at {backup}: {error}"
            ) from error
        shutil.rmtree(backup, ignore_errors=True)
        raise
    shutil.rmtree(backup, ignore_errors=True)


def _assemble(config: ProjectConfig, paths: tuple[Path, ...]) -> Path:
    """Keep staging and output replacement inside one cleanup boundary."""
    dist = config.root / "dist"
    if _is_link(dist):
        raise BuildError("dist must not be a symlink or junction")
    previous = dist / "web"
    if previous.exists() and not (previous / "build-manifest.json").is_file():
        raise BuildError(
            "dist/web is not a recognized Plocks output; preserve or move it before building"
        )
    if (dist / "game-web.zip").exists() and not previous.exists():
        raise BuildError(
            "dist/game-web.zip exists without a Plocks website; preserve or move it first"
        )
    with tempfile.TemporaryDirectory(prefix=".plocks-", dir=config.root) as temporary:
        working = Path(temporary)
        staging = working / "game"
        staging.mkdir()
        _stage(config, paths, staging)
        downloaded = working / "downloads"
        for artifact in artifacts():
            if (
                config.runtime_mode == "self-contained"
                or artifact[0].startswith("notices/")
                or artifact[0].endswith((".whl", "favicon.png", "browserfs.min.js", ".json"))
            ):
                asset = download(artifact, downloaded)
                if asset.suffix == ".whl":
                    if asset.name.startswith("pillow-"):
                        _patch_wheel(asset)
                    extract_wheel(asset, staging)
        packed = _package(staging, downloaded)
        website = working / "web"
        _website(config, packed, downloaded, website)
        archive = working / "game-web.zip"
        _normalized_zip(website, archive)
        _publish(website, archive, dist)
    return dist / "web"


def build(path: str | Path, *, self_contained: bool = False) -> Path:
    """Build a website and ZIP without executing project source; failures raise BuildError."""
    try:
        config = load_project(path, self_contained=self_contained)
        paths = collect(config)
        check_source(config, paths)
        return _assemble(config, paths)
    except (OSError, UnicodeError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        raise BuildError(f"Cannot build project: {error}") from error
