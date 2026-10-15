"""Portable selection, deterministic bundles, and preservation on build failure."""

import hashlib
import importlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from plocks import BuildError
from plocks.web.build import build
from plocks.web.collect import check_source, collect
from plocks.web.project import load_project
from plocks.web.runtime import _Artifact, artifacts, download, extract_wheel

builder = importlib.import_module("plocks.web.build")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A game with an entry that would leave evidence if a builder executed it."""
    root = tmp_path / "game"
    root.mkdir()
    (root / "main.py").write_text("open('EXECUTED', 'w').write('bad')\n")
    (root / "assets/nested").mkdir(parents=True)
    (root / "assets/nested/picture.png").write_bytes(b"image fixture")
    (root / "helper.py").write_text("answer = 42\n")
    return root


@pytest.fixture
def packaging(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace only upstream I/O and packing; exercise the actual site assembly."""
    payloads = {
        "0.9.3/favicon.png": b"icon",
        "support/browserfs.min.js": b"/* helper */",
        "0.9.3/pythons.js": b"/* pinned loader */",
        "0.9.3/python.wasm": b"runtime",
        "notices/runtime.txt": b"licensed fixture",
        "index-0.9.3-cp312.json": json.dumps(
            {"-CDN-": "fixture", "pygame": "pygame.whl", "PIL": "pillow.whl"}
        ).encode(),
    }
    inventory = tuple(
        (name, "https://fixture.invalid/" + name, len(data), hashlib.sha256(data).hexdigest())
        for name, data in payloads.items()
    )

    def fetch(artifact: _Artifact, destination: Path) -> Path:
        target = destination / artifact[0]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payloads[artifact[0]])
        return target

    def pack(staging: Path, downloaded: Path) -> Path:
        archive = downloaded / "fixture.apk"
        with zipfile.ZipFile(archive, "w") as output:
            for path in sorted(staging.rglob("*")):
                if path.is_file():
                    output.write(path, "assets/" + path.relative_to(staging).as_posix())
        return archive

    monkeypatch.setattr(builder, "artifacts", lambda: inventory)
    monkeypatch.setattr(builder, "download", fetch)
    monkeypatch.setattr(builder, "_package", pack)


def test_selection_and_custom_entry(project: Path) -> None:
    """Nested modules/assets are selected; hidden, bytecode, and development trees are not."""
    (project / "scripts").mkdir()
    (project / "scripts/start.py").write_text("import helper\n")
    (project / "notes.txt").write_text("include me")
    for directory in (".private", "dist", "build", "venv", "node_modules", "__pycache__"):
        (project / directory).mkdir()
        (project / directory / "ignored.py").write_text("import unsupported_dependency")
    (project / "plocks.toml").write_text(
        '[game]\nentry="scripts/start.py"\ntitle="Custom"\ninclude=["notes.txt"]\n'
    )
    config = load_project(project)
    paths = collect(config)
    assert config.entry == Path("scripts/start.py") and config.title == "Custom"
    assert paths == tuple(
        map(
            Path,
            ("assets/nested/picture.png", "helper.py", "main.py", "notes.txt", "scripts/start.py"),
        )
    )
    check_source(config, paths)


@pytest.mark.parametrize(
    "settings",
    [
        '[game]\nentry="missing.py"',
        '[game]\nentry="../main.py"',
        '[game]\nassets=["absent"]',
        '[game]\nassets="assets"',
        "[game]\ntitle=123",
        "[game]\nunknown=true",
        '[game]\nentry="assets"',
        "game=42",
        "[broken",
    ],
)
def test_invalid_configuration(project: Path, settings: str) -> None:
    """Invalid configuration fails before download or game execution."""
    (project / "plocks.toml").write_text(settings)
    with pytest.raises(BuildError):
        load_project(project)


def test_symlinks_and_path_collisions(project: Path, tmp_path: Path) -> None:
    """Selected links and directory case collisions cannot change meanings across hosts."""
    link = project / "assets/linked.png"
    link.symlink_to(project / "assets/nested/picture.png")
    with pytest.raises(BuildError, match="symlink"):
        collect(load_project(project))
    link.unlink()
    (project / "unselected.bin").symlink_to(project / "assets/nested/picture.png")
    assert Path("unselected.bin") not in collect(load_project(project))
    selected = tmp_path / "linked-game"
    selected.symlink_to(project, target_is_directory=True)
    with pytest.raises(BuildError, match="symlink"):
        load_project(selected)
    # Directly supply paths to the walker on case-insensitive macOS too.
    config = load_project(project)
    from unittest.mock import patch

    with (
        patch(
            "plocks.web.collect._walk",
            return_value=[Path("main.py"), Path("A/x.py"), Path("a/y.py")],
        ),
        pytest.raises(BuildError, match="collision"),
    ):
        collect(config)


@pytest.mark.parametrize(
    "source,match",
    [
        ("import numpy", "unsupported browser import"),
        ("from threading import Thread", "unsupported browser import"),
        ("from plocks import Sprite as Actor\nActor('missing.png')", "missing from the bundle"),
        ("import plocks as sp\nsp.Sound('missing.ogg')", "missing from the bundle"),
        ("from plocks import Costume\nCostume('../secret.png')", "missing from the bundle"),
        ("this is invalid python !", "Cannot parse"),
    ],
)
def test_static_portability_checks(project: Path, source: str, match: str) -> None:
    """Identifiable unsupported imports and missing literal assets get actionable diagnostics."""
    (project / "main.py").write_text(source)
    config = load_project(project)
    with pytest.raises(BuildError, match=match):
        check_source(config, collect(config))


def test_audio_and_computed_asset_policy(project: Path) -> None:
    """Foreign audio is rejected; computed paths are deliberately left to runtime checks."""
    (project / "assets/wrong.mp3").write_bytes(b"not portable")
    with pytest.raises(BuildError, match="OGG/Vorbis"):
        collect(load_project(project))
    (project / "assets/wrong.mp3").unlink()
    (project / "assets/wrong.ogg").write_bytes(b"OggS\x00OpusHead")
    with pytest.raises(BuildError, match="another OGG codec"):
        collect(load_project(project))
    (project / "assets/wrong.ogg").unlink()
    (project / "main.py").write_text("from plocks import Sprite\nSprite('assets/' + str(1))")
    config = load_project(project)
    check_source(config, collect(config))


def test_bundle_identity_repeatability_and_no_execution(project: Path, packaging: None) -> None:
    """ZIP/site match, manifests verify, and repeated builds preserve sources and bytes."""
    before = {
        path.relative_to(project): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    }
    website = build(project, self_contained=True)
    assert not (project / "EXECUTED").exists()
    assert (website / "runtime/cdn/0.9.3/python.wasm").read_bytes() == b"runtime"
    assert (website / "notices/runtime.txt").is_file()
    manifest = json.loads((website / "build-manifest.json").read_text())
    for record in manifest["files"]:
        data = (website / record["path"]).read_bytes()
        assert len(data) == record["size"]
        assert hashlib.sha256(data).hexdigest() == record["sha256"]
    with zipfile.ZipFile(website.parent / "game-web.zip") as archive:
        assert "index.html" in archive.namelist()
        assert set(archive.namelist()) == {
            p.relative_to(website).as_posix() for p in website.rglob("*") if p.is_file()
        }
        for name in archive.namelist():
            assert archive.read(name) == (website / name).read_bytes()
    first = (website.parent / "game-web.zip").read_bytes()
    build(project, self_contained=True)
    assert (website.parent / "game-web.zip").read_bytes() == first
    assert all((project / name).read_bytes() == data for name, data in before.items())
    with zipfile.ZipFile(website / "game.apk") as game:
        assert game.read("assets/game/helper.py") == b"answer = 42\n"
        assert b"runpy.run_path" in game.read("assets/main.py")


def test_cdn_and_previous_output_survives_failure(
    project: Path, packaging: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed rebuild leaves both previous successful outputs intact."""
    website = build(project)
    assert not (website / "runtime").exists()
    assert "https://pygame-web.github.io/cdn/0.9.3/" in (website / "site.js").read_text()
    original = (website.parent / "game-web.zip").read_bytes()

    def fail(staging: Path, downloaded: Path) -> Path:
        raise BuildError("injected packaging failure")

    monkeypatch.setattr(builder, "_package", fail)
    with pytest.raises(BuildError, match="injected"):
        build(project)
    assert (website.parent / "game-web.zip").read_bytes() == original
    assert not list(project.glob(".plocks-*"))


def test_publish_rollback_and_unowned_output(
    project: Path, packaging: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replacement failures roll both artifacts back; unrelated directories are preserved."""
    website = build(project)
    original = (website.parent / "game-web.zip").read_bytes()
    replace = os.replace
    calls = 0

    def fail_once(source: str | Path, destination: str | Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 4:
            raise OSError("injected disk failure")
        replace(source, destination)

    monkeypatch.setattr(builder.os, "replace", fail_once)
    with pytest.raises(BuildError, match="disk failure"):
        build(project)
    assert (website.parent / "game-web.zip").read_bytes() == original
    (website / "build-manifest.json").unlink()
    with pytest.raises(BuildError, match="not a recognized"):
        build(project)


def test_failed_rollback_keeps_previous_artifacts(
    project: Path, packaging: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second filesystem failure cannot cause temporary cleanup to delete recovery data."""
    website = build(project)
    previous_zip = (website.parent / "game-web.zip").read_bytes()
    previous_manifest = (website / "build-manifest.json").read_bytes()
    replace = os.replace
    calls = 0

    def fail_twice(source: str | Path, destination: str | Path) -> None:
        nonlocal calls
        calls += 1
        if calls in (4, 5):
            raise OSError("filesystem still unavailable")
        replace(source, destination)

    monkeypatch.setattr(builder.os, "replace", fail_twice)
    with pytest.raises(BuildError, match="previous artifacts are preserved"):
        build(project)
    backups = tuple((project / "dist").glob(".plocks-backup-*"))
    assert len(backups) == 1
    assert (backups[0] / "game-web.zip").read_bytes() == previous_zip
    assert (backups[0] / "web/build-manifest.json").read_bytes() == previous_manifest


def test_artifact_digest_and_wheel_safety(tmp_path: Path) -> None:
    """Artifact digests and wheel traversal checks apply before content is trusted."""
    source = tmp_path / "upstream"
    source.write_bytes(b"expected")
    artifact = ("loader.js", source.as_uri(), 8, hashlib.sha256(b"expected").hexdigest())
    assert download(artifact, tmp_path / "download").read_bytes() == b"expected"
    source.write_bytes(b"tampered")
    with pytest.raises(BuildError, match="changed or is damaged"):
        download(artifact, tmp_path / "download")
    wheel = tmp_path / "unsafe.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("../escape.py", "bad")
    with pytest.raises(BuildError, match="Unsafe wheel"):
        extract_wheel(wheel, tmp_path / "extract")


def test_pinned_notices_ship_with_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Versioned license notices are verified from package resources without network I/O."""

    def unexpected_network(url: object, **options: object) -> None:
        raise AssertionError("A shipped license must not require a network request")

    monkeypatch.setattr("urllib.request.urlopen", unexpected_network)
    notices = [record for record in artifacts() if record[0].startswith("notices/")]
    assert len(notices) >= 5
    for record in notices:
        result = download(record, tmp_path)
        assert hashlib.sha256(result.read_bytes()).hexdigest() == record[3]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows directory junctions")
def test_windows_junctions_cannot_escape_collection_or_output(
    project: Path, tmp_path: Path
) -> None:
    """Directory junctions cannot collect outside files or redirect completed build outputs."""
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "private.py"
    sentinel.write_text("must not be bundled or replaced")
    link = project / "assets/linked"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(outside)], check=True, capture_output=True
    )
    with pytest.raises(BuildError, match="link"):
        collect(load_project(project))
    link.rmdir()
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(project / "dist"), str(outside)],
        check=True,
        capture_output=True,
    )
    with pytest.raises(BuildError, match="dist"):
        build(project)
    assert sentinel.read_text() == "must not be bundled or replaced"
