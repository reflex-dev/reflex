"""yield-streaming handler racing a background task on the same var; abrupt tab close mid-stream."""
import sys, time
from pathlib import Path
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import *
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3180"
REPORT = sys.argv[2] if len(sys.argv) > 2 else "logs/stream.json"
MARKERS = Path(sys.argv[3] if len(sys.argv) > 3 else "markers")
import os
SHOTS = os.environ.get("SHOTS", "../shots")  # outside the app dir: a file written under it hot-reloads the dev server
os.makedirs(SHOTS, exist_ok=True)
results = []
cap = Capture()
clear_markers(MARKERS)
with browser() as b:
    ctx, page = new_page(b, cap)
    page.goto(BASE + "/stream", wait_until="networkidle"); page.wait_for_timeout(1000)
    page.click("#btn-both")
    seen = set()
    t0 = time.time()
    while time.time() - t0 < 30:
        seen.add(page.inner_text("#ticks"))
        if page.inner_text("#ticks") == "ticks: 25" and page.inner_text("#bg-running") == "bg_running: false":
            break
        page.wait_for_timeout(100)
    shared = page.inner_text("#shared")
    print("ticks seen:", len(seen), "final shared:", shared)
    check("yield streaming shows intermediate ticks", len(seen) >= 8, f"{len(seen)} distinct tick values seen", results)
    check("stream + background race: final shared == 25 + 300 (no lost updates)", shared == "shared: 325", shared, results)
    check("background finished flag", page.inner_text("#bg-running") == "bg_running: false", page.inner_text("#bg-running"), results)
    page.screenshot(path=SHOTS + "/stream_page.png")

    # abrupt close mid-stream while background runs
    clear_markers(MARKERS)
    ctx2, page2 = new_page(b, cap)
    page2.goto(BASE + "/stream", wait_until="networkidle"); page2.wait_for_timeout(800)
    page2.click("#btn-reset"); wait_text(page2, "#shared", "shared: 0")
    page2.click("#btn-both"); page2.wait_for_timeout(1500)
    page2.close()
    time.sleep(14)
m = read_markers(MARKERS)
print("markers after close:", m)
results.append({"name": "info: stream/bg markers after abrupt close", "status": "pass", "details": str(m)})
check("background task completes after client closed mid-stream", m.get("bg_race_done") == 1, str(m), results)
sys.exit(finish(results, cap, REPORT))
