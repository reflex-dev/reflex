"""Drive the #7230 router-mutation-guard app.

Usage: s_r7230.py <base_url> <outdir>
"""

import sys
import time

sys.argv = [sys.argv[0], "r7230", *sys.argv[1:]]
from playwright.sync_api import sync_playwright  # noqa: E402
from wsdrive import BASE, OUT, attach, delta_keys, deltas, dump, log, txt  # noqa: E402

BENIGN = ("Hey developer", "connecting", "connected", "React DevTools", "Disconnect websocket")


def lines(page):
    return [e.inner_text() for e in page.query_selector_all(".logline")]


def since(t0, tag):
    for t, c, n, pl in deltas(t0):
        k = delta_keys(pl)
        if k:
            log(f"    [{tag}] delta:", k)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    page = ctx.new_page()
    attach(page, "c1")
    page.goto(f"{BASE}/?a=1&b=two", wait_until="networkidle")
    page.wait_for_selector("#routeview", timeout=30000)
    time.sleep(1.0)
    log("routeview:", txt(page, "#routeview"))
    log("onload   :", txt(page, "#onload"))

    for btn, tag in [
        ("#plain", "plain"),
        ("#bgroot", "bgroot"),
        ("#bgsub", "bgsub"),
        ("#subplain", "subplain"),
        ("#bgread", "bgread"),
        ("#bgnested", "bgnested"),
    ]:
        t0 = time.time()
        page.click(btn)
        page.wait_for_timeout(1200)
        log(f"== {tag} ==")
        since(t0, tag)
        for ln in lines(page):
            log("   ", ln)
        log(f"   ticks={txt(page, '#ticks')} subticks={txt(page, '#subticks')}")
        log("    routeview:", txt(page, "#routeview"))
        page.click("#clear")
        page.wait_for_timeout(300)

    page.screenshot(path=str(OUT / "r7230_after.png"))

    # (e) ordinary router reads: client-side nav + direct load
    t0 = time.time()
    page.click("#tolink")
    page.wait_for_timeout(1200)
    log("== client-side nav to /other?q=1 ==")
    log("    routeview:", txt(page, "#routeview"))
    log("    onload   :", txt(page, "#onload"))
    page.goto(f"{BASE}/other?q=direct", wait_until="networkidle")
    page.wait_for_timeout(1000)
    log("== direct load /other?q=direct ==")
    log("    routeview:", txt(page, "#routeview"))
    log("    onload   :", txt(page, "#onload"))
    page.screenshot(path=str(OUT / "r7230_other.png"))

    dump("r7230")
    from wsdrive import console_log, errors, net  # noqa: E402

    log("== console (non-benign) ==")
    for line in console_log:
        if any(s in line for s in BENIGN):
            continue
        log("  ", line)
    log("== pageerrors ==", errors)
    log("== net ==", net)
    ctx.close()
    b.close()
