"""Tests for the experimental incremental compile cache (in-process page cache)."""

from reflex.compiler import page_cache


def test_global_epoch_tracks_global_files(tmp_path):
    (tmp_path / "rxconfig.py").write_text("config = 1\n")
    (tmp_path / "other.py").write_text("x = 1\n")
    epoch = page_cache.global_epoch(root=tmp_path)
    # editing a non-global file does NOT change the epoch
    (tmp_path / "other.py").write_text("x = 2\n")
    assert page_cache.global_epoch(root=tmp_path) == epoch
    # editing a genuinely-global file (rxconfig.py) DOES
    (tmp_path / "rxconfig.py").write_text("config = 2\n")
    assert page_cache.global_epoch(root=tmp_path) != epoch


def _dummy_page():  # a page-like callable defined in this module
    return None


def test_page_module_files_resolves(tmp_path):
    files = page_cache.page_module_files([_dummy_page])
    assert any(p.name == "test_page_cache.py" for p in files)


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


def test_validate_page_fine_grained_deps():
    page_cache.clear_page_store()
    ctx = object()
    dep = "/proj/state.py"
    # page depends on file `dep` at content hash H1, under global epoch "e1"
    page_cache.store_page("/x", "e1", {dep: "H1"}, ctx, True)
    # all deps unchanged + epoch matches -> hit
    assert page_cache.validate_page("/x", "e1", lambda p: {dep: "H1"}.get(p)) == (
        ctx,
        True,
    )
    # a dependency file changed -> miss
    assert page_cache.validate_page("/x", "e1", lambda p: {dep: "H2"}.get(p)) is None
    # the genuinely-global epoch changed -> miss
    assert page_cache.validate_page("/x", "e2", lambda p: {dep: "H1"}.get(p)) is None


def test_validate_page_with_no_deps_only_tracks_epoch():
    page_cache.clear_page_store()
    ctx = object()
    # page depends on NO files
    page_cache.store_page("/x", "e1", {}, ctx, False)
    # some unrelated file changed -> page is still a hit (it depends on nothing)
    assert page_cache.validate_page("/x", "e1", lambda p: "Z") == (ctx, False)
    # the global epoch changed -> miss
    assert page_cache.validate_page("/x", "e2", lambda p: "Z") is None
    # no stored entry -> miss
    page_cache.clear_page_store()
    assert page_cache.validate_page("/x", "e1", lambda p: None) is None


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
