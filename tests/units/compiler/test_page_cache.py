"""Tests for the per-page dependency graph used by the incremental compile cache."""

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
