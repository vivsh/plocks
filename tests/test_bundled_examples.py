"""Installed-resource lookup and safe source copying without repository assumptions."""

import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from plocks import cli
from plocks._examples import _copy, _example, _names


def command(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> int:
    """Call the same CLI parser used by the installed console entry point."""
    monkeypatch.setattr("sys.argv", ["plocks", *arguments])
    return cli.main()


def test_installed_catalog_and_copy_are_available_from_any_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Listing and copying include each real game's assets and skip removed games."""
    monkeypatch.chdir(tmp_path)
    assert command(monkeypatch, "examples") == 0
    listed = capsys.readouterr().out.splitlines()
    assert listed == list(_names()) and len(listed) == 14
    assert "dojo_duel" not in listed and "sunset_sprint" not in listed
    assert command(monkeypatch, "examples", "platformer", "--copy-to", "my-game") == 0
    assert (tmp_path / "my-game/main.py").read_bytes() == _example("platformer").joinpath(
        "main.py"
    ).read_bytes()
    assert (tmp_path / "my-game/assets/hero.png").is_file()
    assert not list((tmp_path / "my-game").rglob("__pycache__"))


@pytest.mark.parametrize("spelling", ["platformer", "examples/platformer"])
def test_bundled_run_keeps_resources_alive_during_child_execution(
    spelling: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both supported spellings resolve installed files rather than the caller's directory."""
    monkeypatch.chdir(tmp_path)
    roots: list[Path] = []

    def run(project: Path) -> int:
        assert (project / "main.py").is_file() and (project / "assets/hero.png").is_file()
        roots.append(project)
        return 7

    monkeypatch.setattr(cli, "_run", run)
    assert command(monkeypatch, "run", spelling) == 7 and roots


def test_existing_local_project_wins_over_bundled_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An existing local project is selected, and invalid local projects never fall back."""
    monkeypatch.chdir(tmp_path)
    local = tmp_path / "platformer"
    local.mkdir()
    (local / "main.py").write_text("raise SystemExit(3)")
    assert command(monkeypatch, "run", "platformer") == 3
    (local / "main.py").unlink()
    assert command(monkeypatch, "run", "platformer") == 1


def test_copy_preserves_existing_work_and_rejects_unknown_names(tmp_path: Path) -> None:
    """Copy never merges or overwrites, and invalid names do not create a destination."""
    destination = tmp_path / "mine"
    destination.mkdir()
    (destination / "main.py").write_text("keep my game")
    with pytest.raises(FileExistsError):
        _copy("platformer", destination)
    assert (destination / "main.py").read_text() == "keep my game"
    for name in ("missing", "../platformer", "dojo_duel", "sunset_sprint"):
        with pytest.raises(ValueError, match="Unknown example"):
            _copy(name, tmp_path / "new")
        assert not (tmp_path / "new").exists()


def test_failed_copy_removes_only_its_own_destination(tmp_path: Path) -> None:
    """A failed transfer leaves no partial game or damage to the enclosing folder."""
    marker = tmp_path / "keep.txt"
    marker.write_text("keep")
    with (
        patch("plocks._examples.shutil.copytree", side_effect=OSError("copy failed")),
        pytest.raises(OSError, match="copy failed"),
    ):
        _copy("platformer", tmp_path / "new")
    assert marker.read_text() == "keep" and not (tmp_path / "new").exists()


def test_zipped_resources_are_extracted_and_released_after_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A zip-backed resource stays alive for the child and is cleaned up after it returns."""
    archive = tmp_path / "games.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("demo/main.py", "pass")
        output.writestr("demo/assets/image.txt", "asset")
    seen: list[Path] = []
    monkeypatch.chdir(tmp_path)

    def run(project: Path) -> int:
        assert (project / "assets/image.txt").read_text() == "asset"
        seen.append(project)
        return 0

    with zipfile.ZipFile(archive) as source:
        monkeypatch.setattr(cli, "_example", lambda name: zipfile.Path(source, "demo/"))
        monkeypatch.setattr(cli, "_run", run)
        assert command(monkeypatch, "run", "demo") == 0
    assert seen and not seen[0].exists()
