"""Scenario: #7145 deep self-chain. Usage: s_recursion.py <base_url> <outdir>"""

import sys
import time

sys.argv = [sys.argv[0], "recursion", *sys.argv[1:]]
from playwright.sync_api import sync_playwright  # noqa: E402
from wsdrive import BASE, OUT, attach, dump, log, txt  # noqa: E402

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    page = ctx.new_page()
    attach(page, "c1")
    t_start = time.time()
    page.goto(f"{BASE}/recursion", wait_until="networkidle")
    page.wait_for_selector("#rcn", timeout=30000)

    # let the on_load self-chain run well past the recursion limit
    for i in range(14):
        page.wait_for_timeout(1000)
        log(f"  t+{i + 1}s n={txt(page, '#rcn')} state={txt(page, '#rcstate')}")
        if txt(page, "#rcstate") == "FINISHED":
            break
    log("loop elapsed:", round(time.time() - t_start, 1), "s, n =", txt(page, "#rcn"))
    page.screenshot(path=str(OUT / "recursion_loop_done.png"))

    # start a SECOND deep loop under a superseding root, then navigate mid-run
    page.click("#rcsroot")
    page.wait_for_timeout(2500)
    log("superseding-root loop n =", txt(page, "#rcsn"))
    log("== navigate away (client-side) mid-loop ==")
    page.click("#toother")
    page.wait_for_selector("#otherhere", timeout=20000)
    page.wait_for_timeout(1500)
    log("== navigate back ==")
    page.click("#torecursion")
    page.wait_for_selector("#rcn", timeout=20000)
    page.wait_for_timeout(2500)
    log("after nav back: rc.n =", txt(page, "#rcn"), " rcsuper.n =", txt(page, "#rcsn"))

    # restart the superseding root while the previous one is still running
    page.click("#rcsroot")
    page.wait_for_timeout(1500)
    page.click("#rcsroot")
    page.wait_for_timeout(2000)
    log("after restart: rcsuper.n =", txt(page, "#rcsn"))
    page.click("#rcsstop")
    page.click("#rcstop")
    page.wait_for_timeout(1000)

    # hard reload while a loop is running
    page.click("#rcsroot")
    page.wait_for_timeout(1500)
    page.reload(wait_until="networkidle")
    page.wait_for_selector("#rcn", timeout=30000)
    page.wait_for_timeout(3000)
    log("after reload: rc.n =", txt(page, "#rcn"), " rcsuper.n =", txt(page, "#rcsn"))
    page.click("#rcstop")
    page.click("#rcsstop")
    page.wait_for_timeout(1000)
    page.screenshot(path=str(OUT / "recursion_final.png"))

    dump("recursion")
    from wsdrive import console_log, errors, net  # noqa: E402

    log("== console ==")
    for line in console_log:
        if any(
            s in line
            for s in ("Hey developer", "connecting", "connected", "React DevTools")
        ):
            continue
        log("  ", line)
    log("== pageerrors ==", errors)
    log("== net ==", net)
    ctx.close()
    b.close()
