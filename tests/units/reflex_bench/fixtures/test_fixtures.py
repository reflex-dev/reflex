"""Tests for reflex_bench.fixtures."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from reflex_bench import fixtures
from reflex_bench.schema import FixtureDoc

PLAYGROUND = Path(__file__).parents[4] / "examples" / "playground"


def _files(root: Path) -> set[str]:
    """List the files under a directory.

    Returns:
        POSIX paths relative to ``root``.
    """
    return {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }


def _tracked() -> set[str]:
    """List the playground files git tracks.

    Returns:
        POSIX paths relative to the playground.
    """
    listing = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=PLAYGROUND,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return {path for path in listing.split("\0") if path}


def test_playground_root_is_found_from_the_checkout(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(PLAYGROUND / "playground" / "pages")
    assert fixtures.playground_root().resolve() == PLAYGROUND.resolve()


def test_a_missing_content_hash_raises_a_clear_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError, match=r"examples/playground/\.content-hash"):
        fixtures.playground_root()


def test_the_hash_is_the_committed_line():
    committed = (PLAYGROUND / ".content-hash").read_text(encoding="utf-8").strip()
    assert committed.startswith("sha256:")
    assert fixtures.describe_playground() == {
        "name": "playground",
        "content_hash": committed,
        "params": {},
    }


def test_materialize_playground_copies_the_tracked_files(tmp_path: Path):
    doc = fixtures.materialize_playground(tmp_path / "app")
    assert doc == fixtures.describe_playground()
    copied = _files(tmp_path / "app")
    assert _tracked() - {".content-hash"} <= copied
    assert ".content-hash" not in copied


def test_materialize_playground_skips_build_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "source"
    shutil.copytree(PLAYGROUND, source)
    junk = [
        ".web/package.json",
        ".states/state.pkl",
        "playground/__pycache__/state.cpython-314.pyc",
        "playground/stray.pyc",
        "reflex.db",
        "reflex.lock/bun.lock",
        "uv.lock",
        ".venv/bin/python",
        "uploaded_files/upload.txt",
        "assets/external/reflex/lib.js",
    ]
    # Only assets/external is ignored, not any directory named external.
    kept = ["playground/external/notes.txt", "assets/externals.css"]
    for name in (*junk, *kept):
        (source / name).parent.mkdir(parents=True, exist_ok=True)
        (source / name).write_text("x", encoding="utf-8")
    monkeypatch.setattr(fixtures, "playground_root", lambda: source)
    fixtures.materialize_playground(tmp_path / "app")
    assert _files(tmp_path / "app") == (_tracked() - {".content-hash"}) | set(kept)


def _counting_make(doc: FixtureDoc, made: list[Path]) -> Callable[[Path], FixtureDoc]:
    """Build a ``make`` that writes one file and counts its calls.

    Returns:
        The function.
    """

    def make(dest: Path) -> FixtureDoc:
        dest.mkdir()
        (dest / "rxconfig.py").write_text(doc["content_hash"], encoding="utf-8")
        made.append(dest)
        return doc

    return make


DOC: FixtureDoc = {
    "name": "gen",
    "content_hash": "sha256:" + "1" * 64,
    "params": {"pages": 10},
}


def test_ensure_fixture_reuses_an_app_whose_stamp_matches(tmp_path: Path):
    made: list[Path] = []
    app, doc = fixtures.ensure_fixture(tmp_path, lambda: DOC, _counting_make(DOC, made))
    assert (app, doc) == (tmp_path / "app", DOC)
    assert json.loads((tmp_path / fixtures.STAMP).read_text(encoding="utf-8")) == DOC
    # What priming added to the app survives the reuse.
    (app / ".web").mkdir()
    assert fixtures.ensure_fixture(
        tmp_path, lambda: DOC, _counting_make(DOC, made)
    ) == (app, DOC)
    assert made == [app]
    assert (app / ".web").is_dir()


def test_ensure_fixture_rebuilds_on_a_changed_stamp(tmp_path: Path):
    made: list[Path] = []
    app, _ = fixtures.ensure_fixture(tmp_path, lambda: DOC, _counting_make(DOC, made))
    (app / ".web").mkdir()
    changed: FixtureDoc = {**DOC, "content_hash": "sha256:" + "2" * 64}
    assert fixtures.ensure_fixture(
        tmp_path, lambda: changed, _counting_make(changed, made)
    ) == (app, changed)
    assert made == [app, app]
    assert not (app / ".web").exists()
    assert (app / "rxconfig.py").read_text(encoding="utf-8") == changed["content_hash"]


def test_ensure_fixture_rebuilds_after_an_interrupted_make(tmp_path: Path):
    def broken(dest: Path) -> FixtureDoc:
        dest.mkdir()
        msg = "interrupted"
        raise KeyboardInterrupt(msg)

    fixtures.ensure_fixture(tmp_path, lambda: DOC, _counting_make(DOC, []))
    changed: FixtureDoc = {**DOC, "content_hash": "sha256:" + "2" * 64}
    with pytest.raises(KeyboardInterrupt):
        fixtures.ensure_fixture(tmp_path, lambda: changed, broken)
    # The half-made app carries no stamp, so it is never reused.
    assert not (tmp_path / fixtures.STAMP).exists()
    made: list[Path] = []
    fixtures.ensure_fixture(tmp_path, lambda: DOC, _counting_make(DOC, made))
    assert made == [tmp_path / "app"]


def test_ensure_fixture_rebuilds_a_missing_app(tmp_path: Path):
    made: list[Path] = []
    app, _ = fixtures.ensure_fixture(tmp_path, lambda: DOC, _counting_make(DOC, made))
    shutil.rmtree(app)
    fixtures.ensure_fixture(tmp_path, lambda: DOC, _counting_make(DOC, made))
    assert made == [app, app]


MARKER = '''\
"""A module with two hot reload targets."""

LEAF_MARKER = "m-initial-leaf"  # bench:hmr-target leaf
LEAF_3_MARKER = "m-initial-leaf-3"  # bench:hmr-target leaf-3
OTHER = "m-initial-leaf"
'''


def test_bump_marker_rewrites_exactly_the_pragma_line(tmp_path: Path):
    path = tmp_path / "marker.py"
    path.write_text(MARKER, encoding="utf-8")
    assert fixtures.bump_marker(path, "leaf") == "m-1-leaf"
    assert fixtures.bump_marker(path, "leaf-3") == "m-1-leaf-3"
    assert fixtures.bump_marker(path, "leaf") == "m-2-leaf"
    assert path.read_text(encoding="utf-8") == MARKER.replace(
        '"m-initial-leaf"  # bench:hmr-target leaf\n',
        '"m-2-leaf"  # bench:hmr-target leaf\n',
    ).replace('"m-initial-leaf-3"', '"m-1-leaf-3"')


def test_bump_marker_continues_from_the_value_in_the_file(tmp_path: Path):
    # Every bump changes the file, also for a new run on a reused app.
    path = tmp_path / "marker.py"
    path.write_text('LEAF = "m-41-leaf"  # bench:hmr-target leaf\n', encoding="utf-8")
    assert fixtures.bump_marker(path, "leaf") == "m-42-leaf"
    path.write_text('LEAF = "hand-edited"  # bench:hmr-target leaf\n', encoding="utf-8")
    assert fixtures.bump_marker(path, "leaf") == "m-1-leaf"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (
            'X = "m-initial-root"  # bench:hmr-target root\n',
            "no hot reload target leaf",
        ),
        (MARKER + MARKER, "2 hot reload targets leaf"),
    ],
)
def test_bump_marker_needs_exactly_one_target(tmp_path: Path, text: str, message: str):
    path = tmp_path / "marker.py"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        fixtures.bump_marker(path, "leaf")
    assert path.read_text(encoding="utf-8") == text
