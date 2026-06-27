"""Tests for the experimental persistent compile cache fingerprint."""

from pathlib import Path

from reflex.compiler import page_cache


def _make_project(tmp_path: Path) -> Path:
    (tmp_path / "app.py").write_text("x = 1\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.md").write_text("# hello\n")
    web = tmp_path / ".web"
    web.mkdir()
    (web / "build.js").write_text("// build artifact\n")
    return tmp_path


def test_fingerprint_is_stable(tmp_path):
    root = _make_project(tmp_path)
    assert page_cache.app_source_fingerprint(root) == page_cache.app_source_fingerprint(
        root
    )


def test_fingerprint_ignores_build_dirs(tmp_path):
    root = _make_project(tmp_path)
    fp = page_cache.app_source_fingerprint(root)
    (root / ".web" / "build.js").write_text("// changed artifact\n")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "x.pyc").write_text("junk")
    assert page_cache.app_source_fingerprint(root) == fp


def test_fingerprint_detects_py_change(tmp_path):
    root = _make_project(tmp_path)
    fp = page_cache.app_source_fingerprint(root)
    (root / "app.py").write_text("x = 2\n")
    assert page_cache.app_source_fingerprint(root) != fp


def test_fingerprint_detects_markdown_change(tmp_path):
    root = _make_project(tmp_path)
    fp = page_cache.app_source_fingerprint(root)
    (root / "docs" / "page.md").write_text("# changed\n")
    assert page_cache.app_source_fingerprint(root) != fp


def test_fingerprint_detects_new_file(tmp_path):
    root = _make_project(tmp_path)
    fp = page_cache.app_source_fingerprint(root)
    (root / "extra.py").write_text("y = 3\n")
    assert page_cache.app_source_fingerprint(root) != fp


def test_record_and_is_unchanged(tmp_path, monkeypatch):
    root = _make_project(tmp_path)
    web = root / ".web"
    # has_prior_output() looks for react-router.config.js next to the marker.
    (web / "react-router.config.js").write_text("// config\n")
    monkeypatch.setattr(page_cache.prerequisites, "get_web_dir", lambda: web)

    fp = page_cache.app_source_fingerprint(root)
    assert page_cache.is_unchanged(fp) is False  # nothing recorded yet
    page_cache.record(fp)
    assert page_cache.is_unchanged(fp) is True
    assert page_cache.is_unchanged("different") is False
