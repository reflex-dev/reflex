"""@rx.memo children receiving list/dict from state; count renders via window.__renders.
Compare noop event, unrelated-field update, value-identical reassignment, and real changes."""
import sys, json
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import *
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3180"
REPORT = sys.argv[2] if len(sys.argv) > 2 else "logs/memo.json"
import os
SHOTS = os.environ.get("SHOTS", "../shots")  # outside the app dir: a file written under it hot-reloads the dev server
os.makedirs(SHOTS, exist_ok=True)
results = []
cap = Capture()
counts = {}
with browser() as b:
    ctx, page = new_page(b, cap)
    page.goto(BASE + "/memo", wait_until="networkidle"); page.wait_for_timeout(1500)
    def snap(): return dict(page.evaluate("window.__renders || {}"))
    def delta(label, before, after):
        d = {k: after.get(k, 0) - before.get(k, 0) for k in set(before) | set(after)}
        counts[label] = d
        print(f"  {label}: {d}")
        return d
    base = snap(); print("after load:", base)
    counts["after_load"] = base

    before = snap(); page.click("#btn-noop"); page.wait_for_timeout(1200); d = delta("noop_event", before, snap())
    check("no-op event renders nothing (page/memo render count unchanged)", all(v == 0 for v in d.values()), json.dumps(d), results)

    before = snap(); page.click("#btn-unrelated"); wait_text(page, "#unrelated", "unrelated: 1"); page.wait_for_timeout(500); d = delta("unrelated_update", before, snap())
    check("unrelated-field update does not re-render memo_child(list/dict)", d.get("memo_child", 0) == 0, json.dumps(d), results)
    check("unrelated-field update does re-render memo_scalar", d.get("memo_scalar", 0) >= 1, json.dumps(d), results)

    before = snap(); page.click("#btn-same"); page.wait_for_timeout(1200); d = delta("value_identical_list_reassign", before, snap())
    check("value-identical list reassignment keeps identity (memo_child not re-rendered)", d.get("memo_child", 0) == 0, json.dumps(d), results)

    before = snap(); page.click("#btn-append"); page.wait_for_timeout(1200); d = delta("append_item", before, snap())
    check("real list change re-renders memo_child", d.get("memo_child", 0) >= 1 and "item3" in page.inner_text("#memo-child"), json.dumps(d) + " " + page.inner_text("#memo-child"), results)

    before = snap(); page.click("#btn-meta"); page.wait_for_timeout(1200); d = delta("bump_meta", before, snap())
    check("dict value change re-renders memo_child", d.get("memo_child", 0) >= 1 and "a=2" in page.inner_text("#memo-child"), json.dumps(d) + " " + page.inner_text("#memo-child"), results)

    before = snap(); page.click("#btn-unrelated"); wait_text(page, "#unrelated", "unrelated: 2"); page.wait_for_timeout(500); d = delta("unrelated_update_2", before, snap())
    check("unrelated update after real changes still skips memo_child", d.get("memo_child", 0) == 0, json.dumps(d), results)
    page.screenshot(path=SHOTS + "/memo_page.png")
rc = finish(results, cap, REPORT)
json.dump(counts, open(REPORT.replace(".json", "_counts.json"), "w"), indent=2)
sys.exit(rc)
