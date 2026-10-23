"""Frontend compiled without `Hidden` substate; backend started with EXTRA_SUBSTATE=1 adds it.
Clicking 'call hidden' makes the backend emit a delta for an unknown substate: the frontend must
skip it, keep working, and report it once per connection."""
import sys, os
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import *
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3180"
REPORT = sys.argv[2] if len(sys.argv) > 2 else "logs/unknown_substate.json"
SHOTS = os.environ.get("SHOTS", "../shots"); os.makedirs(SHOTS, exist_ok=True)
results = []
cap = Capture()
with browser() as b:
    ctx, page = new_page(b, cap)
    page.goto(BASE + "/", wait_until="networkidle"); page.wait_for_timeout(1500)
    check("page hydrated with mismatched backend", page.inner_text("#a-log") == "A.log: A.load_tuple_a", page.inner_text("#a-log"), results)
    for i in range(3):
        page.click("#btn-hidden"); page.wait_for_timeout(700)
    page.click("#btn-counter")
    try: wait_text(page, "#counter", "counter: 1", 5); ok = True
    except AssertionError as e: ok = False; print(e)
    check("events still work after unknown-substate deltas", ok, page.inner_text("#counter"), results)
    warns = [m for m in cap.console if "unknown substate" in m["text"]]
    check("frontend warns about unknown substate exactly once per connection", len(warns) == 1, f"{len(warns)} warnings: {[w['text'][:120] for w in warns]}", results)
    errs = [m for m in cap.console if m["type"] == "error"]
    check("no console errors", not errs and not cap.page_errors, f"{errs[:2]} {cap.page_errors[:2]}", results)
    page.reload(wait_until="networkidle"); page.wait_for_timeout(1500)
    page.click("#btn-hidden"); page.wait_for_timeout(1000)
    warns = [m for m in cap.console if "unknown substate" in m["text"]]
    check("new connection reports the unknown substate again (once)", len(warns) == 2, f"{len(warns)} total warnings", results)
    page.click("#btn-counter")
    try: wait_text(page, "#counter", "counter: 2", 5); ok = True
    except AssertionError as e: ok = False; print(e)
    check("events work after reload", ok, page.inner_text("#counter"), results)
    page.screenshot(path=f"{SHOTS}/unknown_substate.png")
# don't count the expected unknown-substate warning as a problem
cap.console = [m for m in cap.console if "unknown substate" not in m["text"]]
sys.exit(finish(results, cap, REPORT))
