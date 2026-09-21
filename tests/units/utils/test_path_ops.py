"""Tests for path operations."""

from pathlib import Path

import pytest

from reflex.utils.path_ops import update_directory_tree, write_file


@pytest.mark.parametrize("string_path", [False, True])
def test_write_file_creates_parents(tmp_path: Path, string_path: bool) -> None:
    """Write UTF-8 content with either a string or Path and missing parents."""
    path = tmp_path / "nested" / "source.js"
    content = 'const message = "hello 🌍";\n'
    write_file(str(path) if string_path else path, content)
    assert path.read_text(encoding="utf-8") == content


def test_write_file_preserves_unchanged_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Identical content must not write or trigger a file-watcher reload."""
    path = tmp_path / "source.js"
    write_file(path, "unchanged")
    original_mtime = path.stat().st_mtime_ns

    def unexpected_write(*args, **kwargs):
        """Reject writes to an unchanged file."""
        pytest.fail("An unchanged file was rewritten")

    monkeypatch.setattr(Path, "write_text", unexpected_write)
    write_file(path, "unchanged")
    assert path.stat().st_mtime_ns == original_mtime


def test_write_file_updates_changed_file(tmp_path: Path) -> None:
    """Existing files receive changed content."""
    path = tmp_path / "source.js"
    write_file(path, "before")
    write_file(path, "after")
    assert path.read_text(encoding="utf-8") == "after"


def test_update_directory_tree_reports_only_copied_files(tmp_path: Path) -> None:
    """Copy callbacks include nested files and omit files skipped on later updates.

    Args:
        tmp_path: The temporary source and destination directories.
    """
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    (source / "nested").mkdir(parents=True)
    (source / "asset.txt").write_text("asset")
    (source / "nested" / "asset.txt").write_text("nested asset")
    copied: list[Path] = []

    update_directory_tree(source, destination, on_copy=copied.append)

    assert set(copied) == {
        destination / "asset.txt",
        destination / "nested" / "asset.txt",
    }
    assert all(path.is_file() for path in copied)
    copied.clear()

    update_directory_tree(source, destination, on_copy=copied.append)

    assert not copied
