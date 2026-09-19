"""Scenario: uncached var + downstream get_delta filter (handover lead).

Usage: s_filtered.py <base_url> <outdir>
"""

import sys
import time

sys.argv = [sys.argv[0], "filtered", *sys.argv[1:]]
from playwright.sync_api import sync_playwright  # noqa: E402
from wsdrive import BASE, OUT, attach, delta_keys, deltas, dump, log, txt  # noqa: E402


def show(page, tag):
    log(
        f"  [{tag}] n={txt(page, '#fln')!r} secret={txt(page, '#flsecret')!r} "
        f"visible={txt(page, '#flvisible')!r}"
    )


def since(t0):
    for t, c, n, pl in deltas(t0):
        k = delta_keys(pl)
        if k:
            log("    delta:", k)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    page = ctx.new_page()
    attach(page, "c1")
    page.goto(f"{BASE}/filtered", wait_until="networkidle")
    page.wait_for_selector("#flsecret", timeout=30000)
    time.sleep(1.0)
    show(page, "load")

    t0 = time.time()
    page.click("#flbump")
    page.wait_for_timeout(400)
    log("== bump while hidden (delta filter drops `secret`) ==")
    since(t0)
    show(page, "after bump n=1")

    t0 = time.time()
    page.click("#flshow")
    page.wait_for_timeout(500)
    log("== show (visible=True): secret SHOULD now be delivered as secret-1 ==")
    since(t0)
    show(page, "after show")
    page.screenshot(path=str(OUT / "filtered_after_show.png"))

    t0 = time.time()
    page.click("#flbump")
    page.wait_for_timeout(400)
    log("== bump again (n=2) ==")
    since(t0)
    show(page, "after bump n=2")

    # and a second hide/bump/show round-trip
    t0 = time.time()
    page.click("#flhide")
    page.wait_for_timeout(300)
    page.click("#flbump")
    page.wait_for_timeout(300)
    page.click("#flshow")
    page.wait_for_timeout(500)
    log("== hide, bump (n=3), show ==")
    since(t0)
    show(page, "after 2nd round")
    page.screenshot(path=str(OUT / "filtered_round2.png"))

    dump("filtered")
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
