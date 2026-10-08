"""Blank-template smoke. Usage: drive_smoke.py <base_url> <outdir> <tag>"""

import sys
import time

from harness import Run, guard_driver_python, wait_for
from playwright.sync_api import sync_playwright

guard_driver_python()
base, outdir, tag = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
run = Run(tag, outdir)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = b.new_page()
    run.attach(page)
    r = page.goto(base + "/")
    run.check("GET / 200", r is not None and r.status == 200, r.status if r else None)
    ok = wait_for(lambda: "Welcome to Reflex!" in page.inner_text("body"), 30)
    run.check("welcome page renders", bool(ok), page.inner_text("body")[:120])
    time.sleep(2)
    before = page.evaluate("document.documentElement.className + ' ' + (document.documentElement.style.colorScheme||'')")
    page.locator("button").first.click()
    time.sleep(1.5)
    after = page.evaluate("document.documentElement.className + ' ' + (document.documentElement.style.colorScheme||'')")
    run.check("colour-mode button toggles", before != after, f"{before!r} -> {after!r}")
    run.shot(page, "index")
    page.reload()
    time.sleep(2)
    after_reload = page.evaluate("document.documentElement.className + ' ' + (document.documentElement.style.colorScheme||'')")
    run.check("colour mode survives reload", after_reload == after, f"{after_reload!r}")
    r2 = page.goto(base + "/nope")
    run.check("unknown route answers 404", r2 is not None and r2.status == 404, r2.status if r2 else None)
    run.bad = [x for x in run.bad if not x["url"].endswith("/nope")]
    b.close()
sys.exit(run.finish())
