from pathlib import Path

import pytest

from reflex.utils import path_ops


def test_link_or_copy_creates_symlink(tmp_path: Path) -> None:
    """link_or_copy creates a symlink pointing at the target when possible.

    Args:
        tmp_path: A temporary directory provided by pytest.
    """
    target = tmp_path / "target.txt"
    target.write_text("hello")
    link_name = tmp_path / "link.txt"

    path_ops.link_or_copy(target, link_name)

    assert link_name.is_symlink()
    assert link_name.resolve() == target.resolve()
    assert link_name.read_text() == "hello"


def test_link_or_copy_is_idempotent(tmp_path: Path) -> None:
    """Re-linking an already-correct symlink is a no-op and does not raise.

    Args:
        tmp_path: A temporary directory provided by pytest.
    """
    target = tmp_path / "target.txt"
    target.write_text("hello")
    link_name = tmp_path / "link.txt"

    path_ops.link_or_copy(target, link_name)
    path_ops.link_or_copy(target, link_name)

    assert link_name.is_symlink()
    assert link_name.resolve() == target.resolve()


def test_link_or_copy_falls_back_to_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When symlinking fails, the target is copied instead.

    Args:
        tmp_path: A temporary directory provided by pytest.
        monkeypatch: A pytest fixture for patching.
    """

    def _fail_symlink(self: Path, *args: object, **kwargs: object) -> None:
        msg = "Operation not permitted"
        raise OSError(msg)

    monkeypatch.setattr(Path, "symlink_to", _fail_symlink)

    target = tmp_path / "target.txt"
    target.write_text("hello")
    link_name = tmp_path / "link.txt"

    path_ops.link_or_copy(target, link_name)

    assert link_name.exists()
    assert not link_name.is_symlink()
    assert link_name.read_text() == "hello"


def test_link_or_copy_copies_directory_on_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A directory target is copied recursively when symlinking fails.

    Args:
        tmp_path: A temporary directory provided by pytest.
        monkeypatch: A pytest fixture for patching.
    """

    def _fail_symlink(self: Path, *args: object, **kwargs: object) -> None:
        msg = "Operation not permitted"
        raise OSError(msg)

    monkeypatch.setattr(Path, "symlink_to", _fail_symlink)

    target = tmp_path / "target_dir"
    target.mkdir()
    (target / "nested.txt").write_text("nested")
    link_name = tmp_path / "link_dir"

    path_ops.link_or_copy(target, link_name)

    assert link_name.is_dir()
    assert not link_name.is_symlink()
    assert (link_name / "nested.txt").read_text() == "nested"


def test_link_or_copy_replaces_stale_copy_with_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A previously copied destination is replaced by a symlink once possible.

    Args:
        tmp_path: A temporary directory provided by pytest.
        monkeypatch: A pytest fixture for patching.
    """
    target = tmp_path / "target.txt"
    target.write_text("hello")
    link_name = tmp_path / "link.txt"

    original_symlink_to = Path.symlink_to

    def _fail_symlink(self: Path, *args: object, **kwargs: object) -> None:
        msg = "Operation not permitted"
        raise OSError(msg)

    monkeypatch.setattr(Path, "symlink_to", _fail_symlink)
    path_ops.link_or_copy(target, link_name)
    assert not link_name.is_symlink()

    monkeypatch.setattr(Path, "symlink_to", original_symlink_to)
    path_ops.link_or_copy(target, link_name)
    assert link_name.is_symlink()
    assert link_name.resolve() == target.resolve()
