"""Tests for reflex_bench.drivers.editor."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from reflex_bench import fixtures
from reflex_bench.drivers import editor
from reflex_bench.drivers.editor import Edit, find_target, text_target


@pytest.fixture
def app(tmp_path: Path) -> Path:
    """Copy the real playground, whose pragma lines the benchmarks rewrite.

    Returns:
        The copy.
    """
    return Path(shutil.copytree(fixtures.playground_dir(), tmp_path / "app"))


@pytest.mark.parametrize(
    ("name", "relative"),
    [
        ("leaf", "playground/components/marker.py"),
        ("root", "playground/layout.py"),
        ("handler", "playground/state.py"),
    ],
)
def test_find_target_on_the_playground(app: Path, name: str, relative: str):
    target = find_target(app, name)
    path = app / relative
    assert target.path == path
    assert target.literal == f"m-initial-{name}"
    assert target.original == path.read_bytes()
    line = path.read_text().splitlines()[target.line_no - 1]
    assert line.endswith(f"# bench:hmr-target {name}")
    start, end = target.span
    assert target.original[start:end] == target.literal.encode()


def test_find_target_skips_build_output(app: Path):
    # A copy of a pragma inside .web must never be the target.
    (app / ".web").mkdir()
    (app / ".web" / "aaa.py").write_text('X = "m-web"  # bench:hmr-target leaf\n')
    assert find_target(app, "leaf").path == app / "playground/components/marker.py"


def test_find_target_rejects_unknown_names(app: Path):
    with pytest.raises(LookupError, match="bench:hmr-target nope"):
        find_target(app, "nope")


def test_find_target_needs_a_string_literal(tmp_path: Path):
    (tmp_path / "app.py").write_text("X = 1  # bench:hmr-target leaf\n")
    with pytest.raises(ValueError, match="no string literal"):
        find_target(tmp_path, "leaf")


def test_text_targets_of_the_assets(app: Path):
    css = text_target(
        app / "assets" / "playground.css", "0.75rem", after=".bench-hooks {"
    )
    lines = css.original.decode().splitlines()
    assert lines[css.line_no - 1].strip() == "font-size: 0.75rem;"
    svg = text_target(app / "assets" / "logo.svg", "<svg")
    assert svg.line_no == 1
    assert svg.span == (0, 4)


def test_text_target_not_found(app: Path):
    with pytest.raises(LookupError, match=r"'0\.75rem' not found after '\.missing \{'"):
        text_target(app / "assets" / "playground.css", "0.75rem", after=".missing {")
    with pytest.raises(LookupError, match="'9rem' not found in"):
        text_target(app / "assets" / "playground.css", "9rem")


def test_prepare_rewrites_only_the_literal(app: Path):
    target = find_target(app, "leaf")
    content = Edit(target).prepare("m-0123456789ab")
    expected = target.original.replace(b'"m-initial-leaf"', b'"m-0123456789ab"')
    assert content == expected
    assert target.path.read_bytes() == target.original


def test_write_is_one_replace_right_after_t0(
    app: Path, monkeypatch: pytest.MonkeyPatch
):
    events: list[tuple[str, object]] = []
    real_replace, real_fsync, real_time_ns = Path.replace, os.fsync, editor.time.time_ns

    def replace(src: Path, dst: Path) -> Path:
        events.append(("replace", (src, dst)))
        return real_replace(src, dst)

    def fsync(fd: int) -> None:
        events.append(("fsync", fd))
        real_fsync(fd)

    def time_ns() -> int:
        now = real_time_ns()
        events.append(("t0", now))
        return now

    # Path.replace is os.replace: one rename(2).
    monkeypatch.setattr(Path, "replace", replace)
    monkeypatch.setattr(os, "fsync", fsync)
    monkeypatch.setattr(editor.time, "time_ns", time_ns)
    target = find_target(app, "leaf")
    edit = Edit(target)
    edit.prepare("m-0123456789ab")
    assert events == []  # building the content touches nothing
    t0 = edit.write()
    assert [name for name, _ in events] == ["fsync", "t0", "replace"]
    assert events[1] == ("t0", t0)
    src, dst = events[2][1]  # pyright: ignore[reportGeneralTypeIssues]
    # A sibling on the same file system, named so file watchers ignore it
    # (watchfiles' default filter skips names ending in "~").
    assert src.parent == dst.parent == target.path.parent
    assert src.name.endswith("~")
    assert dst == target.path
    assert not src.exists()
    assert b'"m-0123456789ab"' in target.path.read_bytes()
    assert edit.edited
    # The restore is timed the same way.
    events.clear()
    restored_at = edit.restore()
    assert [name for name, _ in events] == ["fsync", "t0", "replace"]
    assert events[1] == ("t0", restored_at)


def test_restore_is_byte_identical(app: Path):
    target = find_target(app, "root")
    edit = Edit(target)
    edit.prepare("m-0123456789ab")
    edit.write()
    assert target.path.read_bytes() != target.original
    edit.restore()
    assert target.path.read_bytes() == target.original
    assert not edit.edited
    assert not [p for p in target.path.parent.iterdir() if p.name.endswith("~")]


def test_write_needs_prepare(app: Path):
    with pytest.raises(RuntimeError, match="prepare"):
        Edit(find_target(app, "leaf")).write()
