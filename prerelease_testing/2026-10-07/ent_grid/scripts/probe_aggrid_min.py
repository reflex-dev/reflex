"""Report header texts of the two grids in apps/aggrid_min after a full page load and after a reload.

Usage: probe_aggrid_min.py <base_url> <out_dir> <expected_venv> <label>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session, assert_driver_and_server  # noqa: E402

base, out, venv, label = sys.argv[1:5]
info = assert_driver_and_server(venv)


def headers(p, gid):
    return [h for h in p.locator(f'[grid-id="{gid}"] .ag-header-cell-text').all_inner_texts() if h.strip()]


with Session(f"probe_aggrid_min-{label}", Path(out)) as s:
    s.note(f"guard: {info['versions']}")
    p = s.new_page(label="min")
    for i in range(2):
        if i == 0:
            p.goto(base + "/", wait_until="networkidle")
        else:
            p.reload(wait_until="networkidle")
        p.wait_for_timeout(4000)
        st, lit = headers(p, "state_cols"), headers(p, "literal_cols")
        s.check(f"load {i + 1}: grid with column_defs=State var shows its columns", st == ["Make", "Price"], {"state_cols": st, "literal_cols": lit})
        s.check(f"load {i + 1}: grid with literal column_defs shows its columns", lit == ["Make", "Price"], lit)
    s.shot(p, "after-reload")
