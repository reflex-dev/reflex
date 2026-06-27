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


def _dummy_page():  # a page-like callable defined in this module
    return None


def test_page_module_files_resolves(tmp_path):
    files = page_cache.page_module_files([_dummy_page])
    assert any(p.name == "test_page_cache.py" for p in files)


def test_shared_fingerprint_excludes_page_files(tmp_path):
    (tmp_path / "page.py").write_text("PAGE = 1\n")
    (tmp_path / "shared.py").write_text("SHARED = 1\n")
    page_files = {(tmp_path / "page.py").resolve()}
    fp = page_cache.shared_fingerprint(page_files, root=tmp_path)
    # editing the excluded page file does NOT change the shared fingerprint
    (tmp_path / "page.py").write_text("PAGE = 2\n")
    assert page_cache.shared_fingerprint(page_files, root=tmp_path) == fp
    # editing a shared file DOES
    (tmp_path / "shared.py").write_text("SHARED = 2\n")
    assert page_cache.shared_fingerprint(page_files, root=tmp_path) != fp


def test_page_key_varies_with_shared():
    k = page_cache.page_key(_dummy_page, "sharedA")
    assert page_cache.page_key(_dummy_page, "sharedA") == k  # stable
    assert page_cache.page_key(_dummy_page, "sharedB") != k  # shared change


def test_page_store_roundtrip():
    page_cache.clear_page_store()
    sentinel = object()
    assert page_cache.get_cached_page("/x", "k1") is None
    page_cache.store_page("/x", "k1", sentinel, True)
    assert page_cache.get_cached_page("/x", "k1") == (sentinel, True)
    assert page_cache.get_cached_page("/x", "different") is None  # key mismatch
    page_cache.clear_page_store()
    assert page_cache.get_cached_page("/x", "k1") is None


def _fake_ctx(pages, imports=None, memo=None, stateful=None, wraps=None):
    from types import SimpleNamespace

    return SimpleNamespace(
        compiled_pages={r: SimpleNamespace(output_code=c) for r, c in pages.items()},
        all_imports=imports or {},
        auto_memo_components=memo or {},
        stateful_routes=stateful or {},
        app_wrap_components=wraps or {},
    )


def test_verify_diff_identical():
    from reflex.compiler import compiler

    a = _fake_ctx({"/": "CODE", "/x": "Y"})
    b = _fake_ctx({"/": "CODE", "/x": "Y"})
    assert compiler._diff_compile_contexts(a, b) == []


def test_verify_diff_detects_page_change():
    from reflex.compiler import compiler

    a = _fake_ctx({"/": "OLD"})
    b = _fake_ctx({"/": "NEW"})
    assert "page:/" in compiler._diff_compile_contexts(a, b)


def test_verify_diff_detects_missing_route_and_memo():
    from reflex.compiler import compiler

    a = _fake_ctx({"/": "C"}, memo={("Memo", None): 1})
    b = _fake_ctx({"/": "C", "/x": "C"}, memo={})
    diffs = compiler._diff_compile_contexts(a, b)
    assert any(d.startswith("routes:") for d in diffs)
    assert "auto_memo_components" in diffs
