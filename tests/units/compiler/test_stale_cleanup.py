"""Tests for the memo manifest-driven stale file cleanup."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from reflex.compiler import utils as compiler_utils


@pytest.fixture
def fake_web_dir(tmp_path: Path):
    """Pretend tmp_path is the project's .web directory.

    Args:
        tmp_path: The pytest tmp directory.

    Yields:
        The path used as ``.web`` for the duration of the test.
    """
    web_dir = tmp_path / ".web"
    web_dir.mkdir()
    with patch.object(compiler_utils, "get_web_dir", return_value=web_dir):
        yield web_dir


@pytest.fixture
def relative_web_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Use a relative ``.web`` dir, matching the default get_web_dir() value.

    The other tests mock an absolute web dir, which hides path-joining bugs
    that only surface when ``.web`` is the default relative path.

    Args:
        tmp_path: The pytest tmp directory.
        monkeypatch: The pytest monkeypatch fixture.

    Yields:
        The relative ``.web`` path used for the duration of the test.
    """
    monkeypatch.chdir(tmp_path)
    web_dir = Path(".web")
    web_dir.mkdir()
    with patch.object(compiler_utils, "get_web_dir", return_value=web_dir):
        yield web_dir


def _seed_manifest(web_dir: Path, paths: list[str]) -> None:
    (web_dir / compiler_utils._MEMO_MANIFEST_FILENAME).write_text(
        json.dumps(paths), encoding="utf-8"
    )


def _seed_files(web_dir: Path, relative_paths: list[str]) -> list[Path]:
    written: list[Path] = []
    for rel in relative_paths:
        target = web_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("// memo", encoding="utf-8")
        written.append(target)
    return written


def test_prune_removes_files_dropped_between_runs(fake_web_dir: Path):
    survivor, removed = _seed_files(
        fake_web_dir,
        ["myapp/widgets/buttons.jsx", "myapp/dropped.jsx"],
    )
    _seed_manifest(fake_web_dir, ["myapp/widgets/buttons.jsx", "myapp/dropped.jsx"])

    compiler_utils.prune_stale_memo_files([survivor])

    assert survivor.exists()
    assert not removed.exists()


def test_prune_cleans_empty_parent_dirs(fake_web_dir: Path):
    survivor, _orphan = _seed_files(
        fake_web_dir,
        ["myapp/keep.jsx", "myapp/widgets/orphan.jsx"],
    )
    _seed_manifest(fake_web_dir, ["myapp/keep.jsx", "myapp/widgets/orphan.jsx"])

    compiler_utils.prune_stale_memo_files([survivor])

    assert not (fake_web_dir / "myapp" / "widgets").exists()
    assert (fake_web_dir / "myapp").exists()


def test_prune_only_touches_manifest_paths(fake_web_dir: Path):
    untouched = fake_web_dir / "user_added.jsx"
    untouched.write_text("// stays", encoding="utf-8")
    [survivor] = _seed_files(fake_web_dir, ["myapp/keep.jsx"])
    # Manifest only mentions the survivor — even if other files exist next to
    # it, prune must never delete files outside the manifest's history.
    _seed_manifest(fake_web_dir, ["myapp/keep.jsx"])

    compiler_utils.prune_stale_memo_files([survivor])

    assert untouched.exists()
    assert survivor.exists()


def test_prune_writes_new_manifest(fake_web_dir: Path):
    [survivor] = _seed_files(fake_web_dir, ["myapp/widgets/buttons.jsx"])
    _seed_manifest(fake_web_dir, [])

    compiler_utils.prune_stale_memo_files([survivor])

    manifest = json.loads(
        (fake_web_dir / compiler_utils._MEMO_MANIFEST_FILENAME).read_text(
            encoding="utf-8"
        )
    )
    assert manifest == ["myapp/widgets/buttons.jsx"]


def test_prune_handles_missing_previous_manifest(fake_web_dir: Path):
    [survivor] = _seed_files(fake_web_dir, ["myapp/widgets/buttons.jsx"])

    # No manifest seeded — should not raise and should still write one.
    compiler_utils.prune_stale_memo_files([survivor])

    assert (fake_web_dir / compiler_utils._MEMO_MANIFEST_FILENAME).exists()


def test_prune_handles_relative_web_dir(relative_web_dir: Path):
    survivor, renamed_from = _seed_files(
        relative_web_dir,
        ["myapp/keep.jsx", "myapp/old_name.jsx"],
    )
    _seed_manifest(relative_web_dir, ["myapp/keep.jsx", "myapp/old_name.jsx"])
    # The rename target is written fresh this run and was never in the manifest.
    [renamed_to] = _seed_files(relative_web_dir, ["myapp/new_name.jsx"])

    # The compiler emits ``.web``-prefixed paths (str(get_web_dir() / ...)). With
    # a relative ``.web`` the old is-absolute guard double-prefixed these to
    # ``.web/.web/...``, so emitted keys never matched the manifest: the survivor
    # and rename target were wrongly pruned and the new manifest was corrupted.
    emitted = [
        str(relative_web_dir / "myapp" / "keep.jsx"),
        str(relative_web_dir / "myapp" / "new_name.jsx"),
    ]
    compiler_utils.prune_stale_memo_files(emitted)

    assert survivor.exists()
    assert renamed_to.exists()
    assert not renamed_from.exists()

    manifest = json.loads(
        (relative_web_dir / compiler_utils._MEMO_MANIFEST_FILENAME).read_text(
            encoding="utf-8"
        )
    )
    assert manifest == ["myapp/keep.jsx", "myapp/new_name.jsx"]


def test_prune_ignores_corrupt_manifest(fake_web_dir: Path):
    (fake_web_dir / compiler_utils._MEMO_MANIFEST_FILENAME).write_text(
        "not json", encoding="utf-8"
    )
    [survivor] = _seed_files(fake_web_dir, ["myapp/widgets/buttons.jsx"])

    compiler_utils.prune_stale_memo_files([survivor])

    assert survivor.exists()
