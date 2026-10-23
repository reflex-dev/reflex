"""App B: page reading vars from hundreds of ~2500 substates. Checks render, events, navigation."""
import sys, os, time
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import *
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3181"
REPORT = sys.argv[2] if len(sys.argv) > 2 else "logs/bigstate.json"
SHOTS = os.environ.get("SHOTS", "../shots"); os.makedirs(SHOTS, exist_ok=True)
TAG = sys.argv[3] if len(sys.argv) > 3 else "new"
results = []
cap = Capture()
with browser() as b:
    ctx, page = new_page(b, cap)
    t0 = time.time()
    try:
        page.goto(BASE + "/", wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(2000)
        load_err = None
    except Exception as e:
        load_err = f"{type(e).__name__}: {e}"
    body = ""
    try:
        body = page.inner_text("body")[:300]
    except Exception as e:
        body = f"<unreadable {e}>"
    print("load:", load_err, "| body:", body.replace("\n", " | ")[:200], "| %.1fs" % (time.time() - t0))
    page.screenshot(path=f"{SHOTS}/bigstate_{TAG}.png")
    rendered = False
    try:
        rendered = page.inner_text("#s-7") == "s7=7 state-7" and page.inner_text("#s-299") == "s299=299 state-299" and page.inner_text("#s-last") == "last=2499"
    except Exception as e:
        print("read err", e)
    check("big-state page renders values from substates", rendered, f"load_err={load_err} body={body[:120]!r} page_errors={cap.page_errors[:2]}", results)
    if rendered:
        page.click("#btn-bump7"); 
        try: wait_text(page, "#s-7", "s7=8 state-7", 10); ok = True
        except AssertionError as e: ok = False; print(e)
        check("event on substate 7 updates UI", ok, page.inner_text("#s-7"), results)
        page.click("#btn-bumplast")
        try: wait_text(page, "#s-last", "last=2500", 10); ok = True
        except AssertionError as e: ok = False; print(e)
        check("event on last substate updates UI", ok, page.inner_text("#s-last"), results)
        t1 = time.time(); page.click("#btn-root"); wait_text(page, "#clicks", "clicks: 1", 10); dt = time.time() - t1
        check("root click round-trip", True, f"{dt*1000:.0f} ms", results)
        page.goto(BASE + "/other", wait_until="networkidle"); page.wait_for_timeout(1000)
        check("other page renders", page.inner_text("#s-1000") == "v1000=1000", page.inner_text("#s-1000"), results)
        page.click("text=home"); 
        try: wait_text(page, "#s-7", "s7=8 state-7", 15); ok = True
        except AssertionError as e: ok = False; print(e)
        check("client nav back keeps state", ok, page.inner_text("#s-7"), results)
sys.exit(finish(results, cap, REPORT))
