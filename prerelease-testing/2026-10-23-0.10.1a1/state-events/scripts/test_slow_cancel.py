"""Slow on_load chain (s1 -> s2 -> s3, ~1.7 s each) + background task started from on_load.
Scenario 1: let it finish. Scenario 2: close the tab mid-chain -> chain must stop, bg must finish.
Scenario 3: client-side navigate away mid-chain. Scenario 4: close tab ~immediately after load
(hydration barely started). Markers are files under <app>/markers."""
import sys, time
from pathlib import Path
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import *

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3180"
REPORT = sys.argv[2] if len(sys.argv) > 2 else "logs/slow_cancel.json"
MARKERS = Path(sys.argv[3] if len(sys.argv) > 3 else "markers")
import os
SHOTS = os.environ.get("SHOTS", "../shots")  # outside the app dir: a file written under it hot-reloads the dev server
os.makedirs(SHOTS, exist_ok=True)
results = []
cap = Capture()


def scenario(name, action, wait_after=9.0):
    clear_markers(MARKERS)
    with browser() as b:
        ctx, page = new_page(b, cap)
        page.goto(BASE + "/slow", wait_until="domcontentloaded")
        wait_until(lambda: (MARKERS / "s1_start").exists(), 10, what="s1_start marker")
        t_start = time.time()
        action(page, ctx)
        if not page.is_closed():
            page.wait_for_timeout(int(wait_after * 1000))
        else:
            time.sleep(wait_after)
    m = read_markers(MARKERS)
    print(f"[{name}] markers after {wait_after}s: {m}")
    return m


# 1. let the chain finish
m = scenario("finish", lambda page, ctx: wait_text(page, "#progress", "progress: s3-finished", 12))
check("slow chain completes when client stays", m.get("s3_done") == 1 and m.get("bg_done") == 1, str(m), results)

# 2. close the page while s1 is sleeping
m = scenario("close-mid-s1", lambda page, ctx: (page.wait_for_timeout(600), page.close()))
check("closing tab mid-chain stops later chain steps (s2/s3 never start)", m.get("s2_start") is None and m.get("s3_start") is None, str(m), results)
check("background task started from on_load survives disconnect", m.get("bg_done") == 1, str(m), results)
results.append({"name": "info: s1 marker state after close", "status": "pass", "details": f"s1_done={m.get('s1_done')} (did the in-flight handler run to completion?)"})

# 3. client-side navigate away while s2 is sleeping
def nav_away(page, ctx):
    wait_until(lambda: (MARKERS / "s2_start").exists(), 6, what="s2_start")
    page.wait_for_timeout(300)
    page.click("text=blank")
    wait_text(page, "#blank", "blank", 5)
m = scenario("nav-away-mid-s2", nav_away)
check("client-side navigation mid-chain cancels remaining steps (s3 never starts)", m.get("s3_start") is None, str(m), results)
check("bg task survives navigation", m.get("bg_done") == 1, str(m), results)

# 4. close the page as early as possible (hydration barely started)
clear_markers(MARKERS)
with browser() as b:
    ctx, page = new_page(b, cap)
    page.goto(BASE + "/slow", wait_until="commit")
    page.wait_for_timeout(900)
    page.close()
    time.sleep(8)
m = read_markers(MARKERS)
print("[early-close] markers:", m)
check("early close: no s2/s3 after the client is gone", m.get("s2_start") is None and m.get("s3_start") is None, str(m), results)

# 5. reload mid-chain: new connection should restart on_load; old chain must not double-run
def reload_mid(page, ctx):
    page.wait_for_timeout(500)
    page.reload(wait_until="domcontentloaded")
    wait_text(page, "#progress", "progress: s3-finished", 12)
m = scenario("reload-mid-s1", reload_mid, wait_after=7.0)
check("reload mid-chain: exactly one chain finishes (s3_done == 1), two s1 starts", m.get("s3_done") == 1 and m.get("s1_start") == 2, str(m), results)
with browser() as b:
    ctx, page = new_page(b, cap)
    page.goto(BASE + "/slow", wait_until="networkidle"); page.wait_for_timeout(500)
    page.screenshot(path=SHOTS + "/slow_page.png")
sys.exit(finish(results, cap, REPORT))
