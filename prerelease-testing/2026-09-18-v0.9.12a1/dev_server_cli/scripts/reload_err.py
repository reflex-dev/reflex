"""Keep a page open, break the app module (page-eval error), fix it, check recovery."""

import json
import re
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

BASE, APPFILE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
PORT = int(sys.argv[4])
ev = []


def rec(k, d):
    ev.append({"t": round(time.time(), 2), "k": k, "d": d})
    print(k, "::", d, flush=True)


def ping():
    t = time.time()
    try:
        r = subprocess.run(
            ["curl", "-s", "--noproxy", "*", "-m", "8", "-o", "/dev/null", "-w", "%{http_code}",
             f"http://localhost:{PORT}/ping"], capture_output=True, text=True)
        return r.stdout.strip(), round(time.time() - t, 2)
    except Exception as e:
        return f"ERR{e}", round(time.time() - t, 2)


src = open(APPFILE).read()

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = b.new_context().new_page()
    page.on("console", lambda m: rec("console", f"{m.type}: {m.text[:200]}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: rec("pageerror", str(e)[:300]))
    page.goto(BASE + "/", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(1200)
    rec("heading_before", page.inner_text("#heading"))
    page.click("#inc"); page.wait_for_timeout(400)
    rec("count_before", page.inner_text("#count"))
    rec("ping_before", ping())

    # 1) break it: TypeError from a component constructor at page-eval time
    broken = src.replace('rx.heading(HEADING, id="heading"),',
                         'rx.heading(HEADING, id="heading", bogus_prop=object()),')
    assert broken != src
    open(APPFILE, "w").write(broken)
    rec("edit", "introduced page-eval TypeError")
    time.sleep(8)
    rec("ping_after_break", ping())
    try:
        page.click("#inc", timeout=8000); page.wait_for_timeout(1500)
        rec("count_after_break", page.inner_text("#count"))
    except Exception as e:
        rec("click_after_break_failed", str(e)[:200])
    page.screenshot(path=OUT + "_broken.png")

    # 2) second error: AttributeError
    broken2 = src.replace('rx.heading(HEADING, id="heading"),',
                          'rx.heading(HEADING.no_such_attr, id="heading"),')
    open(APPFILE, "w").write(broken2)
    rec("edit", "introduced AttributeError")
    time.sleep(8)
    rec("ping_after_break2", ping())

    # 3) fix it
    fixed = src.replace('HEADING = "dsc v2"', 'HEADING = "dsc v3-fixed"')
    open(APPFILE, "w").write(fixed)
    rec("edit", "fixed source (HEADING -> dsc v3-fixed)")
    time.sleep(12)
    rec("ping_after_fix", ping())
    try:
        page.reload(wait_until="networkidle", timeout=40000)
        page.wait_for_timeout(2500)
        rec("heading_after_fix", page.inner_text("#heading"))
        page.click("#inc"); page.wait_for_timeout(1200)
        rec("count_after_fix", page.inner_text("#count"))
        rec("RECOVERED", True)
    except Exception as e:
        rec("recover_failed", str(e)[:300])
        rec("RECOVERED", False)
    page.screenshot(path=OUT + "_after_fix.png")
    b.close()

open(OUT + "_events.json", "w").write(json.dumps(ev, indent=1))
