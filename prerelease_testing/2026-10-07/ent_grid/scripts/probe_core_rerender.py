"""Drive the core_rerender app: read the three probes after a full load, after a bump, after client nav.

Usage: probe_core_rerender.py <base_url> <out_dir> <expected_venv> <label>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session, assert_driver_and_server  # noqa: E402

base, out, venv, label = sys.argv[1:5]
info = assert_driver_and_server(venv)
IDS = ["untouched", "touched", "root", "n"]


def snap(p):
    return {i: p.locator(f"#{i}").inner_text() for i in IDS}


with Session(f"probe_core_rerender-{label}", Path(out)) as s:
    s.note(f"guard: {info['versions']}")
    p = s.new_page(label="core")
    res = {}
    p.goto(base + "/", wait_until="networkidle")
    p.wait_for_timeout(3000)
    res["full load"] = snap(p)
    s.check("untouched substate probe re-rendered after hydration (HAS_REFLEX)", res["full load"]["untouched"].startswith("HAS_REFLEX"), res["full load"])
    s.shot(p, "full-load")
    p.reload(wait_until="networkidle")
    p.wait_for_timeout(3000)
    res["reload"] = snap(p)
    p.click("#bump")
    p.wait_for_timeout(1500)
    res["after bump (other var of same substate)"] = snap(p)
    p.click("#to-other")
    p.wait_for_timeout(1500)
    p.click("#to-index")
    p.wait_for_timeout(2000)
    res["after client-side nav back"] = snap(p)
    for k, v in res.items():
        print(f"{k:45s} {json.dumps(v)}")
    s.note(json.dumps(res))
