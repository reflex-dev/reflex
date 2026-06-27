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


def test_shared_fingerprint_excludes_files(tmp_path):
    (tmp_path / "page.py").write_text("PAGE = 1\n")
    (tmp_path / "shared.py").write_text("SHARED = 1\n")
    exclude = {(tmp_path / "page.py").resolve()}
    fp = page_cache.shared_fingerprint(exclude, root=tmp_path)
    # editing an excluded (page/state) file does NOT change the shared fingerprint
    (tmp_path / "page.py").write_text("PAGE = 2\n")
    assert page_cache.shared_fingerprint(exclude, root=tmp_path) == fp
    # editing a non-excluded shared file DOES
    (tmp_path / "shared.py").write_text("SHARED = 2\n")
    assert page_cache.shared_fingerprint(exclude, root=tmp_path) != fp


def test_used_state_files_from_output_and_memos(tmp_path):
    from types import SimpleNamespace

    sfile = (tmp_path / "state.py").resolve()
    mfile = (tmp_path / "mstate.py").resolve()
    id_to_file = {
        "reflex___state____state____app_____s": sfile,
        "reflex___state____state____app_____m": mfile,
    }
    out = 'jsx("div",{},reflex___state____state____app_____s.x_rx_state_)'
    assert page_cache.used_state_files(out, [], id_to_file) == {sfile}
    assert page_cache.used_state_files("no state", [], id_to_file) == set()
    # state hidden inside an auto-memoized component is still captured
    memo = SimpleNamespace(
        render=lambda: {"contents": "reflex___state____state____app_____m.y_rx_state_"}
    )
    assert page_cache.used_state_files(out, [memo], id_to_file) == {sfile, mfile}
    # un-introspectable memo -> conservative (all fine files)
    boom = SimpleNamespace(render=lambda: (_ for _ in ()).throw(RuntimeError()))
    assert page_cache.used_state_files(out, [boom], id_to_file) == {sfile, mfile}


def test_validate_page_fine_grained_state(tmp_path):
    page_cache.clear_page_store()
    ctx = object()
    sf = "/proj/state.py"
    # page used state file sf at hash H1
    page_cache.store_page("/x", "psrc", "shared", {sf: "H1"}, ctx, True)
    # all unchanged -> hit
    assert page_cache.validate_page("/x", "psrc", "shared", {sf: "H1"}) == (ctx, True)
    # the used state file changed -> miss
    assert page_cache.validate_page("/x", "psrc", "shared", {sf: "H2"}) is None
    # page source changed -> miss
    assert page_cache.validate_page("/x", "other", "shared", {sf: "H1"}) is None
    # coarse shared changed -> miss
    assert page_cache.validate_page("/x", "psrc", "other", {sf: "H1"}) is None


def test_validate_page_ignores_unused_state(tmp_path):
    page_cache.clear_page_store()
    ctx = object()
    # page depends on NO state files
    page_cache.store_page("/x", "psrc", "shared", {}, ctx, False)
    # some OTHER state file changed -> page is still a hit (it doesn't use it)
    assert page_cache.validate_page(
        "/x", "psrc", "shared", {"/proj/other_state.py": "Z"}
    ) == (ctx, False)
    page_cache.clear_page_store()
    assert page_cache.validate_page("/x", "psrc", "shared", {}) is None


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
